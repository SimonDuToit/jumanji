import abc
from typing import Tuple

import chex
import jax
import jax.numpy as jnp

from jumanji.environments.routing.lbf import utils
from jumanji.environments.routing.lbf.constants import MOVES
from jumanji.environments.routing.lbf.types import Agent, Observation, State


# todo: check how lbf does action mask - this isn't quite correct:
# An agent can move to another agents spot if that agent also moved
# however we mask out agents current positions.
class LbfObserver(abc.ABC):
    def __init__(self, fov: int, grid_size: int) -> None:
        self._fov = fov
        self._grid_size = grid_size

    @abc.abstractmethod
    def state_to_observation(self, state: State) -> Observation:
        pass


class LbfVectorObserver(LbfObserver):
    def state_to_observation(self, state: State) -> Observation:
        num_food = len(state.foods.level)
        num_agents = len(state.agents.level)

        def make_obs(agent: Agent) -> Tuple[chex.Array, chex.Array]:
            """Make an observation and action mask for a single agent."""

            # Get visible agents that are not self.
            visible_agents = (
                jnp.all(
                    jnp.abs(agent.position - state.agents.position) <= self._fov,
                    axis=-1,
                )
            ) & (agent.id != state.agents.id)
            # Get visible foods that are not eaten.
            visible_foods = (
                jnp.all(
                    jnp.abs(agent.position - state.foods.position) <= self._fov, axis=-1
                )
                & ~state.foods.eaten
            )

            # Placeholder obs for food and agents - this will shown if food or agent is not in view.
            init_vals = jnp.array([-1, -1, 0])
            obs = jnp.tile(init_vals, num_food + num_agents)

            # Get food and agent positions and levels.
            food_ys = jnp.where(visible_foods, state.foods.position[:, 0], -1)
            food_xs = jnp.where(visible_foods, state.foods.position[:, 1], -1)
            food_levels = jnp.where(visible_foods, state.foods.level, 0)

            agent_ys = jnp.where(visible_agents, state.agents.position[:, 0], -1)
            agent_xs = jnp.where(visible_agents, state.agents.position[:, 1], -1)
            agent_levels = jnp.where(visible_agents, state.agents.level, 0)

            # Filter out current agent
            agent_ys_i = jnp.where(agent.id != state.agents.id, size=num_agents - 1)
            agent_xs_i = jnp.where(agent.id != state.agents.id, size=num_agents - 1)
            agent_levels_i = jnp.where(agent.id != state.agents.id, size=num_agents - 1)
            agent_ys = agent_ys[agent_ys_i]
            agent_xs = agent_xs[agent_xs_i]
            agent_levels = agent_levels[agent_levels_i]

            obs = obs.at[jnp.arange(0, 3 * num_food, 3)].set(food_ys)
            obs = obs.at[jnp.arange(1, 3 * num_food, 3)].set(food_xs)
            obs = obs.at[jnp.arange(2, 3 * num_food, 3)].set(food_levels)

            # Current agent always first agent
            obs = obs.at[3 * num_food].set(agent.position[0])
            obs = obs.at[3 * num_food + 1].set(agent.position[1])
            obs = obs.at[3 * num_food + 2].set(agent.level)

            start_idx = 3 * num_food + 3
            end_idx = start_idx + 3 * (num_agents - 1)
            obs = obs.at[jnp.arange(start_idx, end_idx, 3)].set(agent_ys)
            obs = obs.at[jnp.arange(start_idx + 1, end_idx, 3)].set(agent_xs)
            obs = obs.at[jnp.arange(start_idx + 2, end_idx, 3)].set(agent_levels)

            # Get action mask
            next_positions = agent.position + MOVES
            # Is an agent currently in a next position?
            # I know this is a bit complex, any clearer way to do this?
            agent_occupied = jax.vmap(  # vmap over all next_positions
                lambda next_pos: jnp.any(  # check if any agent is in next position
                    # jnp.all to check if next_pos.x == agent.x and next_pos.y == agent.y
                    jnp.all(next_pos == state.agents.position, axis=-1)
                    & (state.agents.id != agent.id)  # agent doesn't block itself
                )
            )(next_positions)
            # Is food currently in a next position?
            food_occupied = jax.vmap(  # vmap over all next_positions
                lambda next_pos: jnp.any(  # check if any agent is in next position
                    # jnp.all to check if next_pos.x == agent.x and next_pos.y == agent.y
                    jnp.all(next_pos == state.foods.position, axis=-1)
                    & ~state.foods.eaten  # food must be uneaten to collide
                )
            )(next_positions)
            # Is the next position out of bounds?
            out_of_bounds = jnp.any(
                (next_positions < 0) | (next_positions >= self._grid_size), axis=-1
            )

            occupied = food_occupied | agent_occupied
            action_mask = ~(occupied | out_of_bounds)

            return obs, action_mask

        obs, action_mask = jax.vmap(make_obs)(state.agents)
        return Observation(
            agents_view=obs, action_mask=action_mask, step_count=state.step_count
        )


class LbfGridObserver(LbfObserver):
    def state_to_observation(self, state: State) -> Observation:
        # get grids with only agents and grid with only foods
        grid = jnp.zeros((self._grid_size, self._grid_size), dtype=jnp.int32)
        agent_grids = jax.vmap(utils.place_agent_on_grid, (0, None))(state.agents, grid)
        food_grids = jax.vmap(utils.place_food_on_grid, (0, None))(state.foods, grid)
        # join all agents into 1 grid and all food into 1 grid
        agent_grid = jnp.sum(agent_grids, axis=0)
        food_grid = jnp.sum(food_grids, axis=0)

        # pad the grid so obs cannot go out of bounds
        agent_grid = jnp.pad(agent_grid, self._fov, constant_values=-1)
        food_grid = jnp.pad(food_grid, self._fov, constant_values=-1)

        # get the indexes to slice in the grid to obtain the view around the agent
        slice_len = 2 * self._fov + 1, 2 * self._fov + 1
        slice_xs, slice_ys = jax.vmap(utils.slice_around, (0, None))(
            state.agents.position, self._fov
        )

        # slice agent and food grids to obtain the view around the agent
        agents_view = jax.vmap(jax.lax.dynamic_slice, in_axes=(None, 0, None))(
            agent_grid, (slice_xs, slice_ys), slice_len
        )
        foods_view = jax.vmap(jax.lax.dynamic_slice, in_axes=(None, 0, None))(
            food_grid, (slice_xs, slice_ys), slice_len
        )
        # compute access mask (action mask in the observation); noop is always available
        access_masks = (agents_view + foods_view) == 0
        access_masks = access_masks.at[:, self._fov, self._fov].set(True)

        # compute action mask
        local_pos = jnp.array([self._fov, self._fov])
        next_local_pos = local_pos + MOVES
        action_mask = access_masks[:, next_local_pos.T[0], next_local_pos.T[1]]

        return Observation(
            agents_view=jnp.stack([agents_view, foods_view, access_masks], axis=1),
            action_mask=action_mask,
            step_count=state.step_count,
        )