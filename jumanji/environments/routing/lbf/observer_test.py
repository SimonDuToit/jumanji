# Copyright 2022 InstaDeep Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import jax.numpy as jnp

from jumanji.environments.routing.lbf.observer import GridObserver, VectorObserver
from jumanji.environments.routing.lbf.types import Food, State

# Levels:
# agent grid
# [1, 2, 0],
# [2, 0, 1],
# [0, 0, 0],

# food grid
# [0, 0, 0],
# [0, 4, 0],
# [3, 0, 0],

# IDs:
# agent grid
# [a0, a1, 0],
# [a2, 0, a3],
# [0, 0, 0],

# food grid
# [0, 0, 0],
# [0, f0, 0],
# [f1, 0, 0],


def test_grid_observer(state: State) -> None:
    observer = GridObserver(fov=1, grid_size=3)
    obs = observer.state_to_observation(state)
    expected_agent_0_view = jnp.array(
        [
            [
                # other agent levels
                [-1, -1, -1],
                [-1, 1, 2],
                [-1, 2, 0],
            ],
            [
                # food levels
                [-1, -1, -1],
                [-1, 0, 0],
                [-1, 0, 4],
            ],
            [
                # access (where can the agent go?)
                [0, 0, 0],
                [0, 1, 0],
                [0, 0, 0],
            ],
        ]
    )

    assert jnp.all(obs.agents_view[0, ...] == expected_agent_0_view)
    assert jnp.all(
        obs.action_mask[0, ...] == jnp.array([True, False, False, False, False, True])
    )

    expected_agent_1_view = jnp.array(
        [
            [
                [-1, -1, -1],
                [1, 2, 0],
                [2, 0, 1],
            ],
            [
                [-1, -1, -1],
                [0, 0, 0],
                [0, 4, 0],
            ],
            [
                [0, 0, 0],
                [0, 1, 1],
                [0, 0, 0],
            ],
        ]
    )
    assert jnp.all(obs.agents_view[1, ...] == expected_agent_1_view)
    assert jnp.all(
        obs.action_mask[1, ...] == jnp.array([True, False, True, False, False, True])
    )

    expected_agent_3_view = jnp.array(
        [
            [
                [2, 0, -1],
                [0, 1, -1],
                [0, 0, -1],
            ],
            [
                [0, 0, -1],
                [4, 0, -1],
                [0, 0, -1],
            ],
            [
                [0, 1, 0],
                [0, 1, 0],
                [1, 1, 0],
            ],
        ]
    )

    assert jnp.all(obs.agents_view[3, ...] == expected_agent_3_view)
    assert jnp.all(
        obs.action_mask[3, ...] == jnp.array([True, True, False, True, False, True])
    )

    # test different fov
    observer = GridObserver(fov=3, grid_size=3)
    # test eaten food is not visible
    eaten = jnp.array([True, False])
    foods = Food(
        eaten=eaten,
        id=state.foods.id,
        position=state.foods.position,
        level=state.foods.level,
    )
    state = state.replace(foods=foods)  # type: ignore

    obs = observer.state_to_observation(state)
    expected_agent_2_view = jnp.array(
        [
            [
                [-1, -1, -1, -1, -1, -1, -1],
                [-1, -1, -1, -1, -1, -1, -1],
                [-1, -1, -1, 1, 2, 0, -1],
                [-1, -1, -1, 2, 0, 1, -1],
                [-1, -1, -1, 0, 0, 0, -1],
                [-1, -1, -1, -1, -1, -1, -1],
                [-1, -1, -1, -1, -1, -1, -1],
            ],
            [
                [-1, -1, -1, -1, -1, -1, -1],
                [-1, -1, -1, -1, -1, -1, -1],
                [-1, -1, -1, 0, 0, 0, -1],
                [-1, -1, -1, 0, 0, 0, -1],
                [-1, -1, -1, 3, 0, 0, -1],
                [-1, -1, -1, -1, -1, -1, -1],
                [-1, -1, -1, -1, -1, -1, -1],
            ],
            [
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 1, 0],
                [0, 0, 0, 1, 1, 0, 0],
                [0, 0, 0, 0, 1, 1, 0],
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
            ],
        ]
    )
    assert jnp.all(obs.agents_view[2, ...] == expected_agent_2_view)
    assert jnp.all(
        obs.action_mask[2, ...] == jnp.array([True, False, True, False, False, True])
    )


def test_vector_observer(state: State) -> None:
    observer = VectorObserver(fov=1, grid_size=3)
    obs = observer.state_to_observation(state)
    expected_agent_0_view = jnp.array(
        [1, 1, 4, -1, -1, 0, 0, 0, 1, 0, 1, 2, 1, 0, 2, -1, -1, 0]
    )
    assert jnp.all(obs.agents_view[0, ...] == expected_agent_0_view)
    assert jnp.all(
        obs.action_mask[0, ...] == jnp.array([True, False, False, False, False, True])
    )

    expected_agent_2_view = jnp.array(
        [1, 1, 4, 2, 0, 3, 1, 0, 2, 0, 0, 1, 0, 1, 2, -1, -1, 0]
    )
    assert jnp.all(obs.agents_view[2, ...] == expected_agent_2_view)
    assert jnp.all(
        obs.action_mask[2, ...] == jnp.array([True, False, False, False, False, True])
    )

    # test different fov
    observer = VectorObserver(fov=3, grid_size=3)
    # test eaten food is not visible
    eaten = jnp.array([True, False])
    foods = Food(
        eaten=eaten,
        id=state.foods.id,
        position=state.foods.position,
        level=state.foods.level,
    )
    state = state.replace(foods=foods)  # type: ignore

    obs = observer.state_to_observation(state)
    expected_agent_3_view = jnp.array(
        [-1, -1, 0, 2, 0, 3, 1, 2, 1, 0, 0, 1, 0, 1, 2, 1, 0, 2]
    )
    assert jnp.all(obs.agents_view[3, ...] == expected_agent_3_view)
    assert jnp.all(
        obs.action_mask[3, ...] == jnp.array([True, True, False, True, True, True])
    )
