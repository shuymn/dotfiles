# MIT License
#
# Copyright (c) 2022 Chance Zibolski
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from kittens.tui.handler import result_handler


def main(args):
    pass


@result_handler(no_ui=True)
def handle_result(args, result, target_window_id, boss):
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return

    direction = args[1]

    neighbors = boss.active_tab.current_layout.neighbors_for_window(
        window, boss.active_tab.windows
    )

    left_neighbors = neighbors.get("left")
    right_neighbors = neighbors.get("right")
    top_neighbors = neighbors.get("top")
    bottom_neighbors = neighbors.get("bottom")

    # has a neighbor on both sides
    if direction == "left" and (left_neighbors and right_neighbors):
        boss.active_tab.resize_window("narrower", 1)
    # only has left neighbor
    elif direction == "left" and left_neighbors:
        boss.active_tab.resize_window("wider", 1)
    # only has right neighbor
    elif direction == "left" and right_neighbors:
        boss.active_tab.resize_window("narrower", 1)

    # has a neighbor on both sides
    elif direction == "right" and (left_neighbors and right_neighbors):
        boss.active_tab.resize_window("wider", 1)
    # only has left neighbor
    elif direction == "right" and left_neighbors:
        boss.active_tab.resize_window("narrower", 1)
    # only has right neighbor
    elif direction == "right" and right_neighbors:
        boss.active_tab.resize_window("wider", 1)

    # has a neighbor above and below
    elif direction == "up" and (top_neighbors and bottom_neighbors):
        boss.active_tab.resize_window("shorter", 1)
    # only has top neighbor
    elif direction == "up" and top_neighbors:
        boss.active_tab.resize_window("taller", 1)
    # only has bottom neighbor
    elif direction == "up" and bottom_neighbors:
        boss.active_tab.resize_window("shorter", 1)

    # has a neighbor above and below
    elif direction == "down" and (top_neighbors and bottom_neighbors):
        boss.active_tab.resize_window("taller", 1)
    # only has top neighbor
    elif direction == "down" and top_neighbors:
        boss.active_tab.resize_window("shorter", 1)
    # only has bottom neighbor
    elif direction == "down" and bottom_neighbors:
        boss.active_tab.resize_window("taller", 1)
