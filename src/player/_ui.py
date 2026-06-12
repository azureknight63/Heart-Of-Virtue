"""UI mixin for Player — skill menu, status display, bars, and the grid helper function."""

import math

import functions  # type: ignore
from narration import colored, cprint, narrate


def generate_output_grid(
    data,
    rows=0,
    cols=0,
    border="*",
    data_color="green",
    data_attr=None,
    border_color="magenta",
    border_attr=None,
):
    """
    Generates a grid from the provided list

    :param data: A list of strings
    :param rows: Number of rows. Will set automatically if left at zero
    :param cols: Number of columns. Will set automatically if left at zero
    :param border: This string pattern will form the border between rows and columns
    :param data_color: The _color and _attr options mirror neotermcolor.colored()
    :param data_attr: Attributes to apply to the data such as normal, bold, dark, underline, blink, reverse, concealed
    :param border_color: Color for the grid border
    :param border_attr: Attributes to apply to the border
    :return: A string formatted in a grid shape
    """
    rows_var = rows
    cols_var = cols
    output = ""
    if (
        rows_var <= 0
    ):  # I don't know how many rows I want, so let's try to find it automatically
        if (
            cols_var > 0
        ):  # I do know how many columns I want, so we can calculate the rows based on that
            rows_var = math.ceil(len(data) / cols_var)
        else:  # I want to figure out the grid arrangement automatically!
            # This will make the grid as "square" as possible
            rows_var = cols_var = math.ceil(math.sqrt(len(data)))
            if (rows_var * cols_var) > (len(data) + cols_var):
                rows_var -= 1
    row_width_compatibility_verified = (
        False  # we will need to make sure the width of the row
    )
    # will fit in the stout display
    cell_max_length = 1
    row_length = 1
    data_raw = data[:]
    for (
        item
    ) in (
        data_raw
    ):  # this will iterate over all the strings in the data list to find the length of
        # the longest one; necessary for padding cells
        item = functions.escape_ansi(item)
        if len(item) > cell_max_length:
            cell_max_length = len(item)

    while (
        not row_width_compatibility_verified
    ):  # this is to make sure the rows don't get too long to display.
        # It will override any row/column parameters
        row_length = ((cell_max_length + len(border) + 2) * cols_var) + len(border)
        if row_length <= 300:
            row_width_compatibility_verified = True
        else:
            cols_var -= 1
            rows_var += 1
        if (
            rows_var == 0
        ):  # this will only happen if the data list contains a really long string over
            # the defined limit.
            rows_var = 1  # In which case, just show all on one line.
            row_width_compatibility_verified = True
            cols_var = len(data)

    data_index = 0
    for row in range(rows_var):
        row_output = (
            colored(
                border * (math.ceil(row_length / len(border))),
                color=border_color,
                attrs=border_attr,
            )
            + "\n"
        )  # insert the row border on top
        for col in range(cols_var):
            try:
                cell_value = data[data_index]
            except IndexError:  # we've reached the end of our data list
                continue
            while (
                len(functions.escape_ansi(cell_value)) < cell_max_length
            ):  # this will pad our cell to the right
                cell_value += " "
            cell_value = colored(cell_value, color=data_color, attrs=data_attr)
            row_output += (
                colored(border, color=border_color, attrs=border_attr)
                + " "
                + cell_value
                + " "
            )
            data_index += 1
        row_output += colored(border, color=border_color, attrs=border_attr)
        output += row_output + "\n"
    output += colored(
        border * (math.ceil(row_length / len(border))),
        color=border_color,
        attrs=border_attr,
    )
    # ^^^ final row border at the bottom
    return output


class PlayerUIMixin:
    """Terminal UI display methods for the Player."""

    def print_status(self):
        """Print Jean's full status: stats, protection, resistances, and susceptibilities."""
        functions.refresh_stat_bonuses(self)
        self.refresh_protection_rating()
        cprint("=====\nStatus\n=====\n" "{}".format(self.name_long), "cyan")
        output_grid_data = [
            "Health: {} / {} ({})".format(self.hp, self.maxhp, self.maxhp_base),
            "Fatigue: {} ({})".format(self.fatigue, self.maxfatigue_base),
            "Weight Tolerance: {} / {} ({})".format(
                self.weight_current,
                self.weight_tolerance,
                self.weight_tolerance_base,
            ),
            "Level: {} // Exp to next: {}".format(self.level, self.exp_to_level),
        ]
        narrate(
            generate_output_grid(
                output_grid_data,
                border="+++",
                border_color="red",
                border_attr=["dark"],
            )
        )

        state_list = ""
        if len(self.states) > 0:
            for state in self.states:
                state_list += colored("{}".format(state.name), "white") + colored(
                    " ({}) ".format(state.steps_left), "red"
                )  # todo test this display
        else:
            state_list = "None"
        cprint("States: {}".format(state_list), "cyan")

        output_grid_data = []
        if self.protection < 0:
            output_grid_data.append(
                "Protection: " + colored("{}".format(self.protection), "red")
            )
        elif self.protection > 0:
            output_grid_data.append(
                "Protection: " + colored("{}".format(self.protection), "green")
            )
        else:
            output_grid_data.append(
                "Protection: " + colored("{}".format(self.protection), "white")
            )

        charstats = [
            "strength",
            "finesse",
            "speed",
            "endurance",
            "charisma",
            "intelligence",
            "faith",
        ]
        for attribute in charstats:
            color = "white"
            if getattr(self, attribute) < getattr(self, attribute + "_base"):
                color = "red"
            elif getattr(self, attribute) > getattr(self, attribute + "_base"):
                color = "green"
            output_grid_data.append(
                "{}: ".format(attribute.title())
                + colored("{} ".format(getattr(self, attribute)), color)
                + colored(
                    "({})".format(getattr(self, attribute + "_base")),
                    "white",
                    attrs=["bold", "dark"],
                )
            )
        narrate(
            generate_output_grid(
                output_grid_data,
                cols=2,
                data_color="white",
                data_attr=["bold", "dark"],
                border="=*=",
            )
        )

        cprint("Vulnerabilities:", "cyan")
        output_grid_data = []
        for n, v in self.resistance.items():
            resistance_value = v * 100
            n += ": "
            while len(n) < 11:
                n += " "  # this will pad the space between the resistance title and value
            if resistance_value == 100:
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="white",
                            attrs=["bold"],
                        )
                    )
                )
            elif 0 <= resistance_value < 100:  # damage reduced
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="blue",
                            attrs=["bold", "dark"],
                        )
                    )
                )
            elif resistance_value > 100:  # damage increased
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="red",
                            attrs=["bold"],
                        )
                    )
                )
            else:  # damage absorbed
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="green",
                            attrs=["bold"],
                        )
                    )
                )
        if len(output_grid_data) == 0:
            narrate("None")
        else:
            narrate(
                generate_output_grid(
                    output_grid_data,
                    border="-",
                    border_color="yellow",
                    border_attr=["bold"],
                )
            )

        cprint("Susceptibilities:", "cyan")
        output_grid_data = []
        for n, v in self.status_resistance.items():
            resistance_value = v * 100
            n += ": "
            while len(n) < 11:
                n += " "  # this will pad the space between the resistance title and value
            if resistance_value == 100:
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="white",
                            attrs=["bold"],
                        )
                    )
                )
            elif 0 <= resistance_value < 100:  # chance reduced
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="blue",
                            attrs=["bold", "dark"],
                        )
                    )
                )
            else:  # chance increased
                output_grid_data.append(
                    n.title()
                    + "{}".format(
                        colored(
                            str(resistance_value) + "%",
                            color="red",
                            attrs=["bold"],
                        )
                    )
                )
        if len(output_grid_data) == 0:
            narrate("None")
        else:
            narrate(
                generate_output_grid(
                    output_grid_data,
                    border="~",
                    border_color="blue",
                    border_attr=["bold"],
                )
            )

        functions.await_input()

    def menu(self):
        """
        Opens the main menu for the player to save, load, or exit the game.
        Executes an autosave before opening the menu.
        """
        functions.autosave(self)
        self.main_menu = True

    def save(self):
        """No-op in the web client.

        Saving is handled by the /api/saves routes; the terminal save menu has
        been removed.
        """
        return

    def commands(self):
        """Print all available room actions with their hotkeys."""
        possible_actions = self.current_room.available_actions()
        for action in possible_actions:
            cprint(
                "{}:{}{}".format(
                    action.name,
                    (" " * (20 - (len(action.name) + 2))),
                    action.hotkey,
                ),
                "blue",
            )
        functions.await_input()

    def show_bars(self, hp=True, fp=True):
        """Show HP and Fatigue bars as coloured block characters."""
        if hp:
            hp_pcnt = float(self.hp) / float(self.maxhp)
            hp_pcnt = int(hp_pcnt * 10)
            hp_string = colored("HP: ", "red") + "["
            for bar in range(0, hp_pcnt):
                hp_string += colored("█", "red")
            for blank in range(hp_pcnt, 10):
                hp_string += " "
            hp_string += "]   "
        else:
            hp_string = ""

        if fp:
            fat_pcnt = float(self.fatigue) / float(self.maxfatigue)
            fat_pcnt = int(fat_pcnt * 10)
            fat_string = colored("FP: ", "green") + "["
            for bar in range(0, fat_pcnt):
                fat_string += colored("█", "green")
            for blank in range(fat_pcnt, 10):
                fat_string += " "
            fat_string += "]"
        else:
            fat_string = ""

        narrate(hp_string + fat_string)
