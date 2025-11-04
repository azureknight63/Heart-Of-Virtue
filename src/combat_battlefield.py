"""
Combat Battlefield Display Window (tkinter-based)

Provides a real-time ASCII art visualization of the combat battlefield during turn-based combat.
Displays combatant positions on a 50×50 square grid using ASCII characters to maintain visual 
consistency with the game's aesthetic.

Features:
- Square grid layout (no scrollbars, resizes with larger maps)
- Facing direction indicators (↑, ↗, →, ↘, ↓, ↙, ←, ↖)
- Health status visualization (! = injured, !! = critical)
- Movement breadcrumb trails showing recent positions
- Color-coded combatants (green=player, cyan=ally, red=enemy, orange/red=injured/critical)
- Dead combatants shown in gray

Character Meanings:
- P/A/E = Combatant character
- ! = Combatant is injured (health < 75%)
- !! = Combatant is critical (health < 25%)
- · = Breadcrumb trail (fading movement history)
- # = Grid boundary markers
"""

import tkinter as tk
from typing import Optional, Dict, List, Any, Tuple, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    from positions import CombatPosition


class CombatBattlefieldWindow:
    """Tkinter-based ASCII grid display for combat positioning with square layout."""

    # Grid dimensions (in characters, not game coordinates)
    GRID_WIDTH = 50
    GRID_HEIGHT = 50
    
    # Character mappings for different combatants
    PLAYER_CHAR = "J"  # Jean, our hero
    ALLY_CHAR = "A"
    ENEMY_CHAR = "E"
    BREADCRUMB_CHAR = "·"
    BORDER_CHAR = "#"
    
    # Direction indicators (compass rose)
    DIRECTION_CHARS = {
        0: "↑",      # N
        45: "↗",     # NE
        90: "→",     # E
        135: "↘",    # SE
        180: "↓",    # S
        225: "↙",    # SW
        270: "←",    # W
        315: "↖",    # NW
    }
    
    # Colors (tkinter color names)
    COLOR_BACKGROUND = "#1e1e1e"
    COLOR_GRID = "#404040"
    COLOR_PLAYER = "#00ff00"      # Green for player
    COLOR_ALLY = "#00ccff"        # Cyan for allies
    COLOR_ENEMY = "#ff3333"       # Red for enemies
    COLOR_INJURED = "#ffaa00"     # Orange for injured
    COLOR_CRITICAL = "#ff6666"    # Bright red for critical
    COLOR_TEXT = "#ffffff"
    COLOR_DEAD = "#666666"        # Gray for dead combatants
    COLOR_BREADCRUMB = "#404040"  # Dark gray for trails

    def __init__(self, title: str = "Combat Battlefield"):
        """
        Initialize the combat battlefield window.
        
        Args:
            title: Window title
        """
        self.title = title
        self.window: Optional[tk.Tk] = None
        self.text_widget: Optional[tk.Text] = None
        self.combatants_data: Dict[str, Dict[str, Any]] = {}
        self.beat_number: int = 0
        self.is_open: bool = False
        
        # Track movement history for breadcrumb trails
        # combatant_name -> deque of positions (max 3 recent positions for minimal clutter)
        self.movement_history: Dict[str, deque] = {}
        
        # Dynamic viewport for showing only relevant area with margin
        self.viewport_x_min: int = 0
        self.viewport_x_max: int = self.GRID_WIDTH - 1
        self.viewport_y_min: int = 0
        self.viewport_y_max: int = self.GRID_HEIGHT - 1
        self.margin: int = 2  # Grid squares of margin around combatants

    def create_window(self) -> None:
        """Create and configure the tkinter window with square grid layout."""
        if self.is_open:
            return

        self.window = tk.Tk()
        self.window.title(self.title)
        # Size for square display with monospace font
        # Using taller window to account for font aspect ratio (char width != char height)
        window_width = 900
        window_height = 900
        self.window.geometry(f"{window_width}x{window_height}")
        self.window.configure(bg=self.COLOR_BACKGROUND)

        # Create main frame
        main_frame = tk.Frame(self.window, bg=self.COLOR_BACKGROUND)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Info header frame
        info_frame = tk.Frame(main_frame, bg=self.COLOR_BACKGROUND)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.info_label = tk.Label(
            info_frame,
            text="Beat: 0 | Combatants: 0",
            bg=self.COLOR_BACKGROUND,
            fg=self.COLOR_TEXT,
            font=("Courier New", 10, "bold")
        )
        self.info_label.pack(side=tk.LEFT)

        # Grid display frame (NO scrollbar - text widget will expand)
        grid_frame = tk.Frame(main_frame, bg=self.COLOR_BACKGROUND)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        # Monospace text widget for ASCII art grid (read-only)
        # Using larger font and adjusted dimensions for square appearance
        self.text_widget = tk.Text(
            grid_frame,
            width=54,  # Initial width (will be dynamic based on viewport)
            height=27,  # Height set for roughly square appearance (2:1 char aspect)
            bg=self.COLOR_BACKGROUND,
            fg=self.COLOR_GRID,  # Default to grid color so breadcrumbs inherit properly
            font=("Courier New", 10),  # Slightly larger font
            wrap=tk.NONE,
            relief=tk.FLAT,
            highlightthickness=0,
            state=tk.DISABLED
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for colors and health status
        self.text_widget.tag_config("player", foreground=self.COLOR_PLAYER, font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("player_injured", foreground=self.COLOR_INJURED, font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("player_critical", foreground=self.COLOR_CRITICAL, font=("Courier New", 10, "bold"))
        
        self.text_widget.tag_config("ally", foreground=self.COLOR_ALLY, font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("ally_injured", foreground=self.COLOR_INJURED, font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("ally_critical", foreground=self.COLOR_CRITICAL, font=("Courier New", 10, "bold"))
        
        self.text_widget.tag_config("enemy", foreground=self.COLOR_ENEMY, font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("enemy_injured", foreground=self.COLOR_INJURED, font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("enemy_critical", foreground=self.COLOR_CRITICAL, font=("Courier New", 10, "bold"))
        
        self.text_widget.tag_config("dead", foreground=self.COLOR_DEAD, font=("Courier New", 10))
        
        # Health marker tags - used for the ! and !! indicators
        # self.text_widget.tag_config("marker_injured", foreground=self.COLOR_INJURED, font=("Courier New", 10, "bold"))
        # self.text_widget.tag_config("marker_critical", foreground=self.COLOR_CRITICAL, font=("Courier New", 10, "bold"))
        
        self.text_widget.tag_config("breadcrumb", foreground=self.COLOR_BREADCRUMB)
        self.text_widget.tag_config("border", foreground=self.COLOR_GRID, font=("Courier New", 10, "bold"))

        # Legend frame
        legend_frame = tk.Frame(main_frame, bg=self.COLOR_BACKGROUND)
        legend_frame.pack(fill=tk.X, pady=(10, 0))

        legend_text = (
            f"Format: [Char][Direction]  {self.PLAYER_CHAR}=Player  {self.ALLY_CHAR}=Ally  {self.ENEMY_CHAR}=Enemy  "
            f"Directions: ↑N ↗NE →E ↘SE ↓S ↙SW ←W ↖NW  "
            f"Colors: Green=Healthy  Orange=Injured  Red=Critical  Gray=Dead  "
            f"{self.BREADCRUMB_CHAR}=Trail"
        )
        legend_label = tk.Label(
            legend_frame,
            text=legend_text,
            bg=self.COLOR_BACKGROUND,
            fg=self.COLOR_TEXT,
            font=("Courier New", 8),
            wraplength=750,
            justify=tk.LEFT
        )
        legend_label.pack(anchor=tk.W)

        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.is_open = True
        
        # Bring window to foreground
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.window.after_idle(self.window.attributes, '-topmost', False)
        
        # Display initial empty grid
        self._render_initial_grid()
        
        self.window.update()

    def on_close(self) -> None:
        """Handle window close event."""
        self.is_open = False
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
            self.text_widget = None

    def close(self) -> None:
        """Close the window gracefully."""
        if self.is_open:
            self.on_close()

    def _render_initial_grid(self) -> None:
        """Render an initial empty grid to display when window first opens."""
        if not self.text_widget:
            return
        
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)
            
            # Create empty grid with borders
            grid_text = self.render_grid()
            self.text_widget.insert(1.0, grid_text)
            
            self.text_widget.config(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _get_direction_char(self, facing_value: int) -> str:
        """Get the direction indicator character for a facing value."""
        # Normalize facing value to 0-360
        facing_value = facing_value % 360
        
        # Find closest direction
        for direction in sorted(self.DIRECTION_CHARS.keys()):
            if abs(facing_value - direction) <= 22.5:
                return self.DIRECTION_CHARS[direction]
        
        return "·"

    def _get_health_indicator(self, health_percent: float) -> str:
        """Get health status indicator suffix."""
        if health_percent < 0.25:
            return "!!"
        elif health_percent < 0.75:
            return "!"
        return ""

    def _get_line_points(self, start_pos: Any, end_pos: Any) -> List[Tuple[int, int]]:
        """
        Get all integer grid points between two positions using Bresenham's line algorithm.
        Includes both start and end points.
        
        Args:
            start_pos: Starting position object with x, y attributes
            end_pos: Ending position object with x, y attributes
            
        Returns:
            List of (x, y) coordinate tuples along the line
        """
        x0 = int(start_pos.x)
        y0 = int(start_pos.y)
        x1 = int(end_pos.x)
        y1 = int(end_pos.y)
        
        points = []
        
        # Bresenham's line algorithm
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        while True:
            points.append((x, y))
            
            if x == x1 and y == y1:
                break
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
        
        return points

    def _update_viewport(self) -> None:
        """Calculate viewport bounds to show all combatants with margin, shrinking the visible area."""
        if not self.combatants_data:
            # No combatants, show full grid
            self.viewport_x_min = 0
            self.viewport_x_max = self.GRID_WIDTH - 1
            self.viewport_y_min = 0
            self.viewport_y_max = self.GRID_HEIGHT - 1
            return
        
        # Find bounds of all combatants
        min_x = self.GRID_WIDTH
        max_x = 0
        min_y = self.GRID_HEIGHT
        max_y = 0
        
        for name, data in self.combatants_data.items():
            pos = data.get("position")
            if pos is None:
                continue
            x = int(pos.x)
            y = int(pos.y)
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
        
        # Also consider movement history
        for name, history in self.movement_history.items():
            for pos in history:
                x = int(pos.x)
                y = int(pos.y)
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
        
        # Ensure we have valid bounds
        if min_x >= self.GRID_WIDTH or max_x < 0 or min_y >= self.GRID_HEIGHT or max_y < 0:
            # All combatants are outside the grid, show full grid
            self.viewport_x_min = 0
            self.viewport_x_max = self.GRID_WIDTH - 1
            self.viewport_y_min = 0
            self.viewport_y_max = self.GRID_HEIGHT - 1
            return
        
        # Apply margin
        self.viewport_x_min = max(0, min_x - self.margin)
        self.viewport_x_max = min(self.GRID_WIDTH - 1, max_x + self.margin)
        self.viewport_y_min = max(0, min_y - self.margin)
        self.viewport_y_max = min(self.GRID_HEIGHT - 1, max_y + self.margin)
        
        # If we're clamped at a boundary, expand in the opposite direction to maintain view size
        # This ensures we always have margin space visible even at edges
        viewport_width = self.viewport_x_max - self.viewport_x_min
        viewport_height = self.viewport_y_max - self.viewport_y_min
        
        # If left edge is at boundary, expand right
        if self.viewport_x_min == 0 and max_x + self.margin < self.GRID_WIDTH - 1:
            desired_width = (max_x + self.margin + 1) - (min_x - self.margin)
            self.viewport_x_max = min(self.GRID_WIDTH - 1, self.viewport_x_min + desired_width + self.margin)
        
        # If right edge is at boundary, expand left
        if self.viewport_x_max == self.GRID_WIDTH - 1 and min_x - self.margin >= 0:
            desired_width = (max_x + self.margin + 1) - (min_x - self.margin)
            self.viewport_x_min = max(0, self.viewport_x_max - desired_width - self.margin)
        
        # If top edge is at boundary, expand down
        if self.viewport_y_min == 0 and max_y + self.margin < self.GRID_HEIGHT - 1:
            desired_height = (max_y + self.margin + 1) - (min_y - self.margin)
            self.viewport_y_max = min(self.GRID_HEIGHT - 1, self.viewport_y_min + desired_height + self.margin)
        
        # If bottom edge is at boundary, expand up
        if self.viewport_y_max == self.GRID_HEIGHT - 1 and min_y - self.margin >= 0:
            desired_height = (max_y + self.margin + 1) - (min_y - self.margin)
            self.viewport_y_min = max(0, self.viewport_y_max - desired_height - self.margin)

    def render_grid(self) -> str:
        """
        Render the current combat state as an ASCII grid with breadcrumbs and facing indicators.
        Dynamically crops to viewport containing combatants with margin.
        
        Returns:
            String representation of the grid
        """
        # Update viewport based on current combatants
        self._update_viewport()
        
        # Calculate visible dimensions
        visible_width = self.viewport_x_max - self.viewport_x_min + 1
        visible_height = self.viewport_y_max - self.viewport_y_min + 1
        
        # Initialize grid with empty spaces
        grid = [[" " for _ in range(visible_width)] for _ in range(visible_height)]
        
        # Track movement direction for each cell to enable diagonal padding
        # (x, y) -> direction tuple (dx, dy) indicating overall movement direction
        grid_directions: Dict[Tuple[int, int], Tuple[int, int]] = {}
        
        # Track combatant positions for overlay (to avoid breadcrumb overwrites)
        combatant_overlay: Dict[Tuple[int, int], str] = {}
        combatant_positions: set = set()  # Track current combatant positions to avoid breadcrumb collision

        # Draw breadcrumb trails first (so they appear under combatants)
        # Breadcrumbs show the complete path including intermediate points between history items
        for name, history in self.movement_history.items():
            history_list = list(history)  # Convert deque to list for easier indexing
            
            # Draw breadcrumbs between consecutive history points
            for i in range(len(history_list) - 1):
                start_pos = history_list[i]
                end_pos = history_list[i + 1]
                
                # Calculate overall movement direction for this segment
                dx = 1 if int(end_pos.x) > int(start_pos.x) else (-1 if int(end_pos.x) < int(start_pos.x) else 0)
                dy = 1 if int(end_pos.y) > int(start_pos.y) else (-1 if int(end_pos.y) < int(start_pos.y) else 0)
                
                # Get all points along the line between these two positions
                line_points = self._get_line_points(start_pos, end_pos)
                
                # Place breadcrumbs on ALL points including start/end (we're showing the complete path)
                for x, y in line_points:
                    # Check if position is in viewport
                    if self.viewport_x_min <= x <= self.viewport_x_max and self.viewport_y_min <= y <= self.viewport_y_max:
                        grid_x = x - self.viewport_x_min
                        grid_y = y - self.viewport_y_min
                        # Mark this as a breadcrumb trail position (don't overwrite existing breadcrumbs)
                        if grid[grid_y][grid_x] == " ":
                            grid[grid_y][grid_x] = self.BREADCRUMB_CHAR
                            # Store the movement direction for this breadcrumb
                            grid_directions[(grid_x, grid_y)] = (dx, dy)

        # Build combatant overlay and track their current positions
        for name, data in self.combatants_data.items():
            pos = data.get("position")
            if pos is None:
                continue

            x = int(pos.x)
            y = int(pos.y)
            
            # Check if position is in viewport
            if not (self.viewport_x_min <= x <= self.viewport_x_max and self.viewport_y_min <= y <= self.viewport_y_max):
                continue
            
            grid_x = x - self.viewport_x_min
            grid_y = y - self.viewport_y_min
            
            # Track this position to avoid breadcrumb collision
            combatant_positions.add((grid_x, grid_y))

            is_alive: bool = data.get("is_alive", True)
            is_player: bool = data.get("is_player", False)
            is_ally: bool = data.get("is_ally", False)
            health_percent: float = data.get("health_percent", 1.0)
            facing_value: int = data.get("facing_value", 0)

            # Determine character to display
            if is_alive:
                if is_player:
                    char = self.PLAYER_CHAR
                elif is_ally:
                    char = self.ALLY_CHAR
                else:
                    char = self.ENEMY_CHAR
            else:
                # Dead combatants shown as lowercase
                if is_player:
                    char = self.PLAYER_CHAR.lower()
                elif is_ally:
                    char = self.ALLY_CHAR.lower()
                else:
                    char = self.ENEMY_CHAR.lower()
            
            # Add facing direction indicator as a suffix
            direction_char = self._get_direction_char(facing_value)
            combined_display = char + direction_char
            
            # Store in overlay (this will overwrite grid values)
            combatant_overlay[(grid_x, grid_y)] = combined_display

        # Apply combatant overlays to grid, but avoid overwriting visible breadcrumbs
        for (grid_x, grid_y), display in combatant_overlay.items():
            if 0 <= grid_y < len(grid) and 0 <= grid_x < len(grid[grid_y]):
                # Always overwrite with combatant (they're the primary focus)
                grid[grid_y][grid_x] = display

        # Ensure consistent 2-character cell width for proper alignment
        # - Combatants (char + direction): 2 chars normally (placed in first char, direction in second)
        # - Combatants with health markers: 3-4 chars, will overflow naturally
        # - Breadcrumbs (·): Pad with character based on movement direction
        #   For horizontal movement: "··" (both cells filled)
        #   For vertical movement: "·" + " " (padding space empty, breadcrumb on next row)
        #   For diagonal movement: "·" + "·" (breadcrumb in diagonal padding cell to show smooth diagonal line)
        for y in range(len(grid)):
            for x in range(len(grid[y])):
                cell = grid[y][x]
                if len(cell) == 1:
                    # Single-char cells need padding
                    if cell == self.BREADCRUMB_CHAR:
                        # Get movement direction for this breadcrumb if available
                        direction = grid_directions.get((x, y), (0, 0))
                        dx, dy = direction
                        
                        if dx != 0 and dy == 0:
                            # Horizontal movement: fill both cells with breadcrumb
                            grid[y][x] = cell + self.BREADCRUMB_CHAR
                        elif dx == 0 and dy != 0:
                            # Vertical movement: breadcrumb stays single char, padding is space
                            grid[y][x] = cell + " "
                        elif dx != 0 and dy != 0:
                            # Diagonal movement: breadcrumb in padding cell for smooth diagonal line
                            grid[y][x] = cell + self.BREADCRUMB_CHAR
                        else:
                            # No direction info: default to double breadcrumb
                            grid[y][x] = cell + self.BREADCRUMB_CHAR
                    else:
                        # Empty spaces get padded with space
                        grid[y][x] = cell + " "
                # Keep cells with 2+ chars as-is (combatants with/without health markers)

        # Convert grid to string with borders
        lines = []
        # Top border
        max_line_width = visible_width * 2 + 2  # Each cell is 2 chars, +2 for borders
        lines.append(self.BORDER_CHAR * max_line_width)

        # Grid content
        for row in grid:
            line_content = "".join(row)
            lines.append(self.BORDER_CHAR + line_content + self.BORDER_CHAR)

        # Bottom border
        lines.append(self.BORDER_CHAR * max_line_width)

        return "\n".join(lines)

    def update_display(self) -> None:
        """Update the displayed grid with current combatant positions and health status."""
        if not self.is_open or not self.text_widget:
            return

        try:
            # Clear text widget
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)

            # Render and insert grid
            grid_text = self.render_grid()
            self.text_widget.insert(1.0, grid_text)

            # Apply color tags FIRST to combatants (so they have highest priority)
            self._apply_color_tags()
            
            # Then apply color tags to grid elements (borders, breadcrumbs)
            # These will NOT override combatant tags since they're lower priority
            self._apply_grid_tags()

            # Update info label - count only alive combatants
            if self.info_label:
                alive_count = sum(1 for data in self.combatants_data.values() if data.get("is_alive", True))
                self.info_label.config(
                    text=f"Beat: {self.beat_number} | Combatants: {alive_count} | "
                         f"Trails: {len(self.movement_history)}"
                )

            self.text_widget.config(state=tk.DISABLED)
            self.window.update()

        except tk.TclError:
            # Window was closed
            self.is_open = False

    def _apply_grid_tags(self) -> None:
        """Apply color tags to borders and breadcrumbs in the grid."""
        if not self.text_widget:
            return

        try:
            # Tag all borders (# characters) and breadcrumbs (· characters)
            # IMPORTANT: Only tag the single character, not the padding that follows
            content = self.text_widget.get(1.0, tk.END)
            
            # Find and tag borders and breadcrumbs
            for line_num, line in enumerate(content.split('\n'), 1):
                for col_num, char in enumerate(line, 1):
                    if char == self.BORDER_CHAR:
                        # Tag only this single character
                        self.text_widget.tag_add("border", f"{line_num}.{col_num - 1}", f"{line_num}.{col_num}")
                    elif char == self.BREADCRUMB_CHAR:
                        # Tag only this single character (not the padding that follows)
                        self.text_widget.tag_add("breadcrumb", f"{line_num}.{col_num - 1}", f"{line_num}.{col_num}")
        except tk.TclError:
            pass

    def _apply_color_tags(self) -> None:
        """Apply color tags to combatant characters based on type and health status."""
        if not self.text_widget:
            return

        # Map combatant names to their tag colors
        # This approach searches for each combatant by their unique display string
        combatant_tags: Dict[str, str] = {}
        
        # Build mapping of display string -> tag for all combatants
        for name, data in self.combatants_data.items():
            is_alive: bool = data.get("is_alive", True)
            is_player: bool = data.get("is_player", False)
            is_ally: bool = data.get("is_ally", False)
            health_percent: float = data.get("health_percent", 1.0)
            display_text: str = data.get("display_text", "")

            # Determine tag to apply based on type and health status
            if not is_alive:
                char_tag = "dead"
            elif is_player:
                if health_percent < 0.25:
                    char_tag = "player_critical"
                elif health_percent < 0.75:
                    char_tag = "player_injured"
                else:
                    char_tag = "player"
            elif is_ally:
                if health_percent < 0.25:
                    char_tag = "ally_critical"
                elif health_percent < 0.75:
                    char_tag = "ally_injured"
                else:
                    char_tag = "ally"
            else:  # Enemy
                if health_percent < 0.25:
                    char_tag = "enemy_critical"
                elif health_percent < 0.75:
                    char_tag = "enemy_injured"
                else:
                    char_tag = "enemy"
            
            # Store tag using display string as key (each combatant's display is unique)
            if display_text:
                combatant_tags[display_text] = char_tag
        
        # Apply color tags by searching for display strings
        for display_text, char_tag in combatant_tags.items():
            try:
                pos = "1.0"
                while True:
                    # Find next occurrence of this display string (e.g., "E↓")
                    pos = self.text_widget.search(display_text, pos, tk.END)
                    if not pos:
                        break
                    
                    # Calculate end position (display_text is 2 characters)
                    line_col = pos.split('.')
                    line = line_col[0]
                    col = int(line_col[1])
                    end_col = col + len(display_text)
                    
                    # Apply the tag
                    self.text_widget.tag_add(char_tag, f"{line}.{col}", f"{line}.{end_col}")
                    
                    # Move past this occurrence
                    pos = f"{line}.{end_col}"
            except (tk.TclError, ValueError, IndexError):
                pass

    def set_combatant(
        self,
        name: str,
        position: Optional[Any],
        is_alive: bool = True,
        is_player: bool = False,
        is_ally: bool = False,
        health_percent: float = 1.0,
        facing_value: int = 0
    ) -> None:
        """
        Update or add a combatant's position on the battlefield.
        
        Args:
            name: Combatant's name (unique identifier)
            position: CombatPosition object or None to remove
            is_alive: Whether the combatant is alive
            is_player: True if this is the player character
            is_ally: True if this is an ally (not an enemy)
            health_percent: Health as fraction (0.0-1.0)
            facing_value: Direction facing in degrees (0-360)
        """
        if position is None:
            if name in self.combatants_data:
                del self.combatants_data[name]
                if name in self.movement_history:
                    del self.movement_history[name]
        else:
            # Update combatant data
            self.combatants_data[name] = {
                "position": position,
                "is_alive": is_alive,
                "is_player": is_player,
                "is_ally": is_ally,
                "health_percent": max(0.0, min(1.0, health_percent)),
                "facing_value": facing_value,
            }
            
            # Pre-calculate display text for use in color tagging
            # Build the display string (char + direction + health markers)
            if is_alive:
                if is_player:
                    char = self.PLAYER_CHAR
                elif is_ally:
                    char = self.ALLY_CHAR
                else:
                    char = self.ENEMY_CHAR
            else:
                if is_player:
                    char = self.PLAYER_CHAR.lower()
                elif is_ally:
                    char = self.ALLY_CHAR.lower()
                else:
                    char = self.ENEMY_CHAR.lower()
            
            direction_char = self._get_direction_char(facing_value)
            display_text = char + direction_char
            
            self.combatants_data[name]["display_text"] = display_text
            
            # Track movement history
            if name not in self.movement_history:
                self.movement_history[name] = deque(maxlen=3)  # Keep only last 3 positions
            
            # Check if position changed and add to history
            history = self.movement_history[name]
            if not history or (history[-1].x != position.x or history[-1].y != position.y):
                try:
                    # Try to copy the position object
                    history.append(position.copy() if hasattr(position, 'copy') else position)
                except (AttributeError, TypeError):
                    # If copy fails, just append the position as-is
                    history.append(position)

    def set_beat(self, beat: int) -> None:
        """
        Update the current beat number display.
        
        Args:
            beat: Current combat beat number
        """
        self.beat_number = beat

    def update_all_combatants(self, player: Any, allies: List[Any], enemies: List[Any]) -> None:
        """
        Bulk update all combatants from combat lists.
        
        Args:
            player: Player object
            allies: List of allied NPCs
            enemies: List of enemy NPCs
        """
        # Build a set of all currently alive combatant names to track
        alive_names = set()
        
        # Update player
        if hasattr(player, "combat_position") and player.combat_position is not None:
            player_name = player.name if hasattr(player, "name") else "Player"
            alive_names.add(player_name)
            
            health_pct = 1.0
            if hasattr(player, "current_health") and hasattr(player, "maxhealth"):
                health_pct = player.current_health / max(1, player.maxhealth)
            
            # Extract facing value - handle Direction enum or raw value
            facing_val = 0
            if hasattr(player.combat_position, "facing"):
                facing = player.combat_position.facing
                if facing is not None:
                    # Try to get value attribute (for enums or objects)
                    if hasattr(facing, "value"):
                        facing_val = facing.value
                    # Or if it's already a number
                    elif isinstance(facing, (int, float)):
                        facing_val = facing
            
            self.set_combatant(
                player_name,
                player.combat_position,
                is_alive=player.is_alive if hasattr(player, "is_alive") else True,
                is_player=True,
                is_ally=True,
                health_percent=health_pct,
                facing_value=facing_val
            )

        # Update allies
        for ally in allies:
            if hasattr(ally, "combat_position") and ally.combat_position is not None:
                ally_name = ally.name if hasattr(ally, "name") else f"Ally_{id(ally)}"
                alive_names.add(ally_name)
                
                health_pct = 1.0
                if hasattr(ally, "current_health") and hasattr(ally, "maxhealth"):
                    health_pct = ally.current_health / max(1, ally.maxhealth)
                
                # Extract facing value - handle Direction enum or raw value
                facing_val = 0
                if hasattr(ally.combat_position, "facing"):
                    facing = ally.combat_position.facing
                    if facing is not None:
                        # Try to get value attribute (for enums or objects)
                        if hasattr(facing, "value"):
                            facing_val = facing.value
                        # Or if it's already a number
                        elif isinstance(facing, (int, float)):
                            facing_val = facing
                
                self.set_combatant(
                    ally_name,
                    ally.combat_position,
                    is_alive=ally.is_alive if hasattr(ally, "is_alive") else True,
                    is_player=False,
                    is_ally=True,
                    health_percent=health_pct,
                    facing_value=facing_val
                )

        # Update enemies
        for enemy in enemies:
            if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                enemy_name = enemy.name if hasattr(enemy, "name") else f"Enemy_{id(enemy)}"
                alive_names.add(enemy_name)
                
                health_pct = 1.0
                if hasattr(enemy, "current_health") and hasattr(enemy, "maxhealth"):
                    health_pct = enemy.current_health / max(1, enemy.maxhealth)
                
                # Extract facing value - handle Direction enum or raw value
                facing_val = 0
                if hasattr(enemy.combat_position, "facing"):
                    facing = enemy.combat_position.facing
                    if facing is not None:
                        # Try to get value attribute (for enums or objects)
                        if hasattr(facing, "value"):
                            facing_val = facing.value
                        # Or if it's already a number
                        elif isinstance(facing, (int, float)):
                            facing_val = facing
                
                self.set_combatant(
                    enemy_name,
                    enemy.combat_position,
                    is_alive=enemy.is_alive if hasattr(enemy, "is_alive") else True,
                    is_player=False,
                    is_ally=False,
                    health_percent=health_pct,
                    facing_value=facing_val
                )
        
        # Remove combatants that are no longer in any list
        # This cleans up dead enemies that were removed from combat_list
        to_remove = []
        for name in self.combatants_data.keys():
            if name not in alive_names:
                to_remove.append(name)
        
        for name in to_remove:
            del self.combatants_data[name]
            if name in self.movement_history:
                del self.movement_history[name]
