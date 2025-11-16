"""
Labyrinth Game - Modernized Version
A turtle-based maze navigation game with enemies, treasures, auto-solve, and level editor features.
"""
import math
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import sleep
from typing import List, Tuple, Optional, Dict, Callable
import turtle


# ==================== CONSTANTS ====================
class Config:
    """Game configuration constants."""
    SCREEN_WIDTH = 1000
    SCREEN_HEIGHT = 1000
    CELL_SIZE = 24
    BACKGROUND_COLOR = "black"
    
    # Colors
    COLOR_WALL = "white"
    COLOR_PLAYER = "blue"
    COLOR_TREASURE = "gold"
    COLOR_ENEMY = "red"
    COLOR_START = "green"
    COLOR_END = "red"
    COLOR_TEXT = "white"
    COLOR_BUTTON = "#2E86AB"
    COLOR_BUTTON_HOVER = "#A23B72"
    
    # Movement
    ENEMY_SPEED = 200
    PLAYER_DETECTION_RADIUS = 100
    COLLISION_DISTANCE = 5
    
    # Scoring
    TREASURE_VALUE = 100
    ENEMY_VALUE = 25
    
    # Grid for creator
    GRID_ROWS = 20
    GRID_COLS = 25


class Direction(Enum):
    """Movement directions."""
    UP = (0, 24)
    DOWN = (0, -24)
    LEFT = (-24, 0)
    RIGHT = (24, 0)
    
    @property
    def dx(self) -> int:
        return self.value[0]
    
    @property
    def dy(self) -> int:
        return self.value[1]
    
    @property
    def opposite(self) -> 'Direction':
        """Return the opposite direction."""
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT
        }
        return opposites[self]
    
    @staticmethod
    def from_string(s: str) -> 'Direction':
        """Convert string to Direction."""
        mapping = {
            "up": Direction.UP,
            "down": Direction.DOWN,
            "left": Direction.LEFT,
            "right": Direction.RIGHT
        }
        return mapping.get(s.lower(), Direction.UP)


# ==================== DATA STRUCTURES ====================
@dataclass
class Position:
    """Represents a position in the maze."""
    x: float
    y: float
    
    def __iter__(self):
        return iter((self.x, self.y))
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate Euclidean distance to another position."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


# ==================== MAZE LOADER ====================
class MazeLoader:
    """Handles loading and parsing maze files."""
    
    @staticmethod
    def load_from_file(filename: str) -> Tuple[List[List[int]], Position, Position]:
        """Load maze from file."""
        with open(filename, 'r') as f:
            maze = []
            start_pos = None
            end_pos = None
            
            for row_idx, line in enumerate(f):
                row = []
                for col_idx, char in enumerate(line):
                    if char == '.':
                        row.append(0)
                    elif char == '#':
                        row.append(1)
                    elif char == 'x':
                        row.append(0)
                        start_pos = Position(row_idx, col_idx)
                    elif char == 'X':
                        row.append(0)
                        end_pos = Position(row_idx, col_idx)
                
                if row:
                    maze.append(row)
        
        return maze, start_pos, end_pos


# ==================== GAME ENTITIES ====================
class Wall(turtle.Turtle):
    """Represents a wall in the maze."""
    
    def __init__(self):
        super().__init__()
        self.shape("square")
        self.color(Config.COLOR_WALL)
        self.penup()
        self.speed(0)


class Player(turtle.Turtle):
    """The player character."""
    
    def __init__(self):
        super().__init__()
        self.penup()  # Ensure no drawing trails
        try:
            self.shape("dragon1.gif")
        except turtle.TurtleGraphicsError:
            self.shape("turtle")
        self.color(Config.COLOR_PLAYER)
        self.speed(0)
        self.gold = 0
        self.move_history: List[Direction] = []
        self.is_auto_mode = False
        self.is_reverse_mode = False
    
    def move(self, direction: Direction, walls: set) -> bool:
        """Move in specified direction if valid."""
        new_pos = Position(
            self.xcor() + direction.dx,
            self.ycor() + direction.dy
        )
        
        if new_pos.to_tuple() not in walls and not self.is_auto_mode and not self.is_reverse_mode:
            self.goto(*new_pos)
            self.move_history.append(direction.opposite)
            return True
        return False
    
    def move_to_direction(self, direction: Direction):
        """Move without validation (for auto mode)."""
        new_pos = Position(
            self.xcor() + direction.dx,
            self.ycor() + direction.dy
        )
        self.goto(*new_pos)
    
    def is_collision(self, other: turtle.Turtle) -> bool:
        """Check collision with another entity."""
        current_pos = Position(self.xcor(), self.ycor())
        other_pos = Position(other.xcor(), other.ycor())
        return current_pos.distance_to(other_pos) < Config.COLLISION_DISTANCE
    
    def destroy(self):
        """Remove player from screen."""
        self.goto(2000, 2000)
        self.hideturtle()


class Treasure(turtle.Turtle):
    """Collectible treasure."""
    
    def __init__(self, x: float, y: float):
        super().__init__()
        self.penup()  # Ensure no drawing trails
        self.shape("circle")
        self.color(Config.COLOR_TREASURE)
        self.speed(0)
        self.gold = Config.TREASURE_VALUE
        self.goto(x, y)
    
    def destroy(self):
        """Remove treasure from screen."""
        self.goto(2000, 2000)
        self.hideturtle()


class Enemy(turtle.Turtle):
    """Enemy that chases the player."""
    
    def __init__(self, x: float, y: float):
        super().__init__()
        self.penup()  # Ensure no drawing trails
        self.shape("circle")
        self.color(Config.COLOR_ENEMY)
        self.speed(0)
        self.gold = Config.ENEMY_VALUE
        self.goto(x, y)
        self.current_direction = random.choice(list(Direction))
        self.walls: set = set()
        self.treasures: set = set()
        self.player_ref: Optional[Player] = None
        self.is_active = True
    
    def set_obstacles(self, walls: set, treasures: set):
        """Set the obstacles for pathfinding."""
        self.walls = walls
        self.treasures = treasures
    
    def set_player(self, player: Player):
        """Set player reference for tracking."""
        self.player_ref = player
    
    def move(self):
        """Move enemy (called periodically)."""
        try:
            if not self.player_ref or not self.is_active:
                return
            
            # Chase player if close
            if self._is_close_to_player():
                self._move_towards_player()
            else:
                self._move_random()
            
            if self.is_active:
                turtle.ontimer(self.move, t=Config.ENEMY_SPEED)
        except (turtle.Terminator, Exception):
            self.is_active = False
            return
    
    def _is_close_to_player(self) -> bool:
        """Check if player is within detection radius."""
        if not self.player_ref:
            return False
        
        current_pos = Position(self.xcor(), self.ycor())
        player_pos = Position(self.player_ref.xcor(), self.player_ref.ycor())
        return current_pos.distance_to(player_pos) < Config.PLAYER_DETECTION_RADIUS
    
    def _move_towards_player(self):
        """Move in direction of player."""
        if not self.player_ref:
            return
        
        if self.player_ref.xcor() < self.xcor():
            self.current_direction = Direction.LEFT
        elif self.player_ref.xcor() > self.xcor():
            self.current_direction = Direction.RIGHT
        elif self.player_ref.ycor() < self.ycor():
            self.current_direction = Direction.DOWN
        elif self.player_ref.ycor() > self.ycor():
            self.current_direction = Direction.UP
        
        self._try_move()
    
    def _move_random(self):
        """Move in random direction."""
        self._try_move()
    
    def _try_move(self):
        """Attempt to move in current direction."""
        new_pos = Position(
            self.xcor() + self.current_direction.dx,
            self.ycor() + self.current_direction.dy
        )
        
        if new_pos.to_tuple() not in self.walls and new_pos.to_tuple() not in self.treasures:
            self.goto(*new_pos)
        else:
            self.current_direction = random.choice(list(Direction))
    
    def destroy(self):
        """Remove enemy from screen."""
        self.is_active = False
        self.goto(2000, 2000)
        self.hideturtle()


class ScoreDisplay(turtle.Turtle):
    """Displays the game score."""
    
    def __init__(self):
        super().__init__()
        self.speed(0)
        self.shape("square")
        self.color(Config.COLOR_TEXT)
        self.penup()
        self.hideturtle()
        self.goto(0, 300)
        self.current_score = 0
        self.high_score = 0
    
    def update(self, score: int):
        """Update the displayed score."""
        self.current_score = score
        if score > self.high_score:
            self.high_score = score
        
        self.clear()
        self.write(
            f"Score: {self.current_score}  Highscore: {self.high_score}",
            align="center",
            font=("Courier", 24, "normal")
        )


# ==================== UI COMPONENTS ====================
class Button:
    """Interactive button component with hover effects."""
    
    def __init__(self, x: float, y: float, width: float, height: float, text: str, 
                 color: str = Config.COLOR_BUTTON):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.color = color
        self.turtle = turtle.Turtle()
        self.turtle.hideturtle()
        self.turtle.penup()
        self.turtle.speed(0)
        self.is_clicked = False
        self.is_hovered = False
    
    def draw(self, hovered: bool = False):
        """Draw the button with optional hover effect."""
        try:
            self.turtle.clear()
            self.turtle.goto(self.x, self.y)
            
            # Fill button background
            self.turtle.fillcolor(Config.COLOR_BUTTON_HOVER if hovered else self.color)
            self.turtle.pencolor(Config.COLOR_TEXT)
            self.turtle.pendown()
            self.turtle.begin_fill()
            
            for _ in range(2):
                self.turtle.forward(self.width)
                self.turtle.left(90)
                self.turtle.forward(self.height)
                self.turtle.left(90)
            
            self.turtle.end_fill()
            self.turtle.penup()
            
            # Draw text centered
            text_x = self.x + self.width / 2
            text_y = self.y + self.height / 3
            self.turtle.goto(text_x, text_y)
            self.turtle.color(Config.COLOR_TEXT)
            self.turtle.write(self.text, align="center", font=("Courier", 16, "bold"))
        except:
            pass
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside button."""
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)
    
    def on_click(self, x: float, y: float) -> bool:
        """Handle click event. Returns True if button was clicked."""
        if self.contains_point(x, y):
            self.is_clicked = True
            return True
        return False
    
    def check_hover(self, x: float, y: float) -> bool:
        """Check if mouse is hovering over button."""
        was_hovered = self.is_hovered
        self.is_hovered = self.contains_point(x, y)
        if was_hovered != self.is_hovered:
            self.draw(self.is_hovered)
        return self.is_hovered


class LevelEditor:
    """Level editor for creating custom mazes."""
    
    def __init__(self, screen: turtle.Screen, blank: bool = False):
        self.screen = screen
        self.blank = blank
        self.selected_item: Optional[str] = None
        self.palette_items: Dict[str, turtle.Turtle] = {}
        self.placed_items: List[Tuple[str, float, float]] = []
        self.grid_layout: List[List[str]] = []
        self.play_button: Optional[Button] = None
        self.clear_button: Optional[Button] = None
        self._init_grid()
        self._setup_palette()
        self._setup_buttons()
    
    def _init_grid(self):
        """Initialize blank grid."""
        if self.blank:
            self.grid_layout = [['.' for _ in range(Config.GRID_COLS)] 
                              for _ in range(Config.GRID_ROWS)]
        else:
            self.grid_layout = []
    
    def _setup_buttons(self):
        """Setup editor control buttons."""
        self.play_button = Button(-600, -200, 120, 50, "PLAY MAP")
        self.play_button.draw()
        
        self.clear_button = Button(-600, -300, 120, 50, "CLEAR ALL")
        self.clear_button.draw()
    
    def _setup_palette(self):
        """Setup the palette with available items."""
        # Wall
        wall = turtle.Turtle()
        wall.penup()
        wall.hideturtle()
        try:
            wall.shape("wall1.gif")
        except:
            wall.shape("square")
        wall.color("white")
        wall.goto(-600, 300)
        wall.stamp()
        self.palette_items['m'] = wall
        
        # Treasure
        treasure = turtle.Turtle()
        treasure.penup()
        treasure.hideturtle()
        treasure.shape("circle")
        treasure.color("yellow")
        treasure.goto(-600, 200)
        treasure.stamp()
        self.palette_items['t'] = treasure
        
        # Enemy
        enemy = turtle.Turtle()
        enemy.penup()
        enemy.hideturtle()
        enemy.shape("circle")
        enemy.color("red")
        enemy.goto(-600, 100)
        enemy.stamp()
        self.palette_items['e'] = enemy
        
        # Start
        start = turtle.Turtle()
        start.penup()
        start.hideturtle()
        start.shape("square")
        start.color("green")
        start.goto(-600, 0)
        start.stamp()
        self.palette_items['s'] = start
        
        # End
        end = turtle.Turtle()
        end.penup()
        end.hideturtle()
        end.shape("square")
        end.color("red")
        end.goto(-600, -100)
        end.stamp()
        self.palette_items['f'] = end
    
    def handle_click(self, x: float, y: float) -> Optional[str]:
        """Handle click in editor mode. Returns action if button clicked."""
        try:
            # Check control buttons
            if self.play_button and self.play_button.contains_point(x, y):
                self.play_button.is_clicked = True
                return 'play'
            if self.clear_button and self.clear_button.contains_point(x, y):
                self.clear_button.is_clicked = True
                self.clear_all()
                return 'clear'
            
            # Check if clicking palette
            if -612 < x < -588:
                if 88 < y < 112:
                    self.selected_item = 'e'
                elif 188 < y < 212:
                    self.selected_item = 't'
                elif 288 < y < 312:
                    self.selected_item = 'm'
                elif -12 < y < 12:
                    self.selected_item = 's'
                elif -112 < y < -88:
                    self.selected_item = 'f'
            else:
                # Place item on grid
                if self.selected_item:
                    cell = self.pixel_to_cell(x, y)
                    if cell and abs(cell[0]) < Config.GRID_COLS//2 and abs(cell[1]) < Config.GRID_ROWS//2:
                        pixel = self.cell_to_pixel(cell[0], cell[1])
                        
                        # Check if tile already has an item (no stacking)
                        tile_occupied = any(px == pixel[0] and py == pixel[1] for _, px, py in self.placed_items)
                        
                        if tile_occupied:
                            # Show error message briefly
                            try:
                                msg = turtle.Turtle()
                                msg.penup()
                                msg.hideturtle()
                                msg.color("orange")
                                msg.goto(0, -450)
                                msg.write("Cannot stack items on same tile!", align="center", font=("Courier", 12, "bold"))
                                self.screen.update()
                                sleep(0.5)
                                msg.clear()
                            except:
                                pass
                            return None
                        
                        # Check start/end limitations
                        if self.selected_item == 's':
                            # Only allow one start
                            if any(item_type == 's' for item_type, _, _ in self.placed_items):
                                try:
                                    msg = turtle.Turtle()
                                    msg.penup()
                                    msg.hideturtle()
                                    msg.color("orange")
                                    msg.goto(0, -450)
                                    msg.write("Only ONE start allowed!", align="center", font=("Courier", 12, "bold"))
                                    self.screen.update()
                                    sleep(0.5)
                                    msg.clear()
                                except:
                                    pass
                                return None
                        
                        if self.selected_item == 'f':
                            # Only allow one end
                            if any(item_type == 'f' for item_type, _, _ in self.placed_items):
                                try:
                                    msg = turtle.Turtle()
                                    msg.penup()
                                    msg.hideturtle()
                                    msg.color("orange")
                                    msg.goto(0, -450)
                                    msg.write("Only ONE end allowed!", align="center", font=("Courier", 12, "bold"))
                                    self.screen.update()
                                    sleep(0.5)
                                    msg.clear()
                                except:
                                    pass
                                return None
                        
                        # Place the item
                        item = self.palette_items.get(self.selected_item)
                        if item:
                            item.goto(pixel[0], pixel[1])
                            item.stamp()
                            item.goto(-600, {
                                'e': 100, 't': 200, 'm': 300, 's': 0, 'f': -100
                            }.get(self.selected_item, 0))
                            self.placed_items.append((self.selected_item, pixel[0], pixel[1]))
        except Exception:
            pass
        return None
    
    def clear_all(self):
        """Clear all placed items."""
        self.placed_items.clear()
        for item in self.palette_items.values():
            item.clear()
        self._setup_palette()
        if self.play_button:
            self.play_button.draw()
        if self.clear_button:
            self.clear_button.draw()
    
    def get_custom_level_layout(self) -> List[str]:
        """Convert placed items to level layout."""
        # Create empty grid
        layout = [['.' for _ in range(Config.GRID_COLS)] for _ in range(Config.GRID_ROWS)]
        
        # Track start and end positions
        start_pos = None
        end_pos = None
        
        # Place items
        for item_type, px, py in self.placed_items:
            cell = self.pixel_to_cell(px, py)
            if cell:
                col = cell[0] + Config.GRID_COLS // 2
                row = cell[1] + Config.GRID_ROWS // 2
                if 0 <= row < Config.GRID_ROWS and 0 <= col < Config.GRID_COLS:
                    if item_type == 'm':
                        layout[row][col] = 'X'
                    elif item_type == 't':
                        layout[row][col] = 'T'
                    elif item_type == 'e':
                        layout[row][col] = 'E'
                    elif item_type == 's':
                        layout[row][col] = 'S'
                        start_pos = (row, col)
                    elif item_type == 'f':
                        layout[row][col] = 'F'
                        end_pos = (row, col)
        
        # Fill perimeter with walls (except start and end)
        for col in range(Config.GRID_COLS):
            # Top row
            if layout[0][col] == '.' and (start_pos is None or (0, col) != start_pos) and (end_pos is None or (0, col) != end_pos):
                layout[0][col] = 'X'
            # Bottom row
            if layout[Config.GRID_ROWS-1][col] == '.' and (start_pos is None or (Config.GRID_ROWS-1, col) != start_pos) and (end_pos is None or (Config.GRID_ROWS-1, col) != end_pos):
                layout[Config.GRID_ROWS-1][col] = 'X'
        
        for row in range(Config.GRID_ROWS):
            # Left column
            if layout[row][0] == '.' and (start_pos is None or (row, 0) != start_pos) and (end_pos is None or (row, 0) != end_pos):
                layout[row][0] = 'X'
            # Right column
            if layout[row][Config.GRID_COLS-1] == '.' and (start_pos is None or (row, Config.GRID_COLS-1) != start_pos) and (end_pos is None or (row, Config.GRID_COLS-1) != end_pos):
                layout[row][Config.GRID_COLS-1] = 'X'
        
        # Convert to strings
        return [''.join(row) for row in layout]
    
    def pixel_to_cell(self, pos_x: float, pos_y: float) -> Optional[List[int]]:
        """Convert pixel coordinates to cell coordinates."""
        # Simplified conversion for grid
        cell_x = round(pos_x / Config.CELL_SIZE)
        cell_y = round(pos_y / Config.CELL_SIZE)
        return [cell_x, cell_y]
    
    def cell_to_pixel(self, x: int, y: int) -> List[float]:
        """Convert cell coordinates to pixel coordinates."""
        return [24 * x, 24 * y]


# ==================== GAME MANAGER ====================
class GameLevel:
    """Represents a game level."""
    
    def __init__(self, layout: List[str], auto_solution: Optional[List[str]] = None):
        self.layout = layout
        self.walls: set = set()
        self.treasures: List[Treasure] = []
        self.treasure_positions: set = set()
        self.enemies: List[Enemy] = []
        self.start_pos: Optional[Position] = None
        self.end_pos: Optional[Position] = None
        self.player_spawn: Optional[Position] = None
        self.auto_solution = auto_solution or []
    
    def get_screen_position(self, row: int, col: int) -> Position:
        """Convert grid position to screen coordinates."""
        screen_x = -(Config.CELL_SIZE * round(len(self.layout[0]) / 2)) + (col * Config.CELL_SIZE)
        screen_y = (Config.CELL_SIZE * round(len(self.layout) / 2)) - (row * Config.CELL_SIZE)
        return Position(screen_x, screen_y)


class Game:
    """Main game manager."""
    
    def __init__(self):
        self.screen = turtle.Screen()
        self.screen.title("LABYRINTHE - Modernized")
        self.screen.bgcolor(Config.BACKGROUND_COLOR)
        self.screen.setup(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)
        self.screen.tracer(0)
        
        # Register shapes
        self._register_shapes()
        
        # Game state
        self.current_level = 0
        self.levels = self._create_levels()
        self.custom_levels: List[GameLevel] = []
        self.player: Optional[Player] = None
        self.score_display: Optional[ScoreDisplay] = None
        self.game_mode: Optional[str] = None  # 'play', 'create', 'select'
        self.auto_mode = False
        self.create_mode = False
        self.level_editor: Optional[LevelEditor] = None
        self.screen_initialized = False
        self.is_running = True
        
        # UI
        self.buttons: Dict[str, Button] = {}
        self.click_handlers: List[Callable] = []
    
    def _register_shapes(self):
        """Register custom shapes if available."""
        try:
            turtle.register_shape("wall1.gif")
            turtle.register_shape("dragon1.gif")
        except Exception:
            pass
    
    def _on_close(self):
        """Handle window close event."""
        self.is_running = False
        import sys
        import os
        try:
            self.screen.bye()
        except:
            pass
        os._exit(0)
    
    def _create_levels(self) -> List[GameLevel]:
        """Create all game levels with auto solutions."""
        level_0 = GameLevel(
            [
                "XXXXXXXXXXXXXXSX",
                "X             PX",
                "FTXXXXXXXXXXXXXX",
                "XXXXXXXXXXXXXXXX"
            ],
            auto_solution=["left"] * 12 + ["down"] + ["left"] * 2
        )
        
        level_1 = GameLevel(
            [
                "XXXXXXXXXXXXXXX",
                "X X XT        F",
                "X X   XXXXXXXXX",
                "XT  X         X",
                "XXXXXXXXXXXXX X",
                "XXXXXXXXXXXXX X",
                "XT          X X",
                "XXXXXXXXXXX   X",
                "XT          X X",
                "XXXXXXXXXXXXX X",
                "XP            X",
                "XXXXXXXXXXXXXXX"
            ],
            auto_solution=["right"] * 12 + ["up"] * 7 + ["left"] * 8 + ["up"] * 2 + ["right"] * 9
        )
        
        level_2 = GameLevel([
            "XXXXXXXXXXXXXXXXXXXXXXXXX",
            "XP XXXXXXX          XXXXX",
            "X  XXXXXXX  XXXXXX  XXXXX",
            "X       XX EXXXXXX EXXXXX",
            "X       XX  XXX        XX",
            "XXXXXX  XX  XXX E      XX",
            "XXXXXX  XX  XXXXXX  XXXXX",
            "XXXXXX  XX    XXXX  XXXXX",
            "X  XXX        XXXXT XXXXX",
            "X  XXX  XXXXXXXXXXXXXXXXX",
            "X         XXXXXXXXXXXXXXX",
            "XE               XXXXXXXX",
            "XXXXXXXXXXXX     XXXXXT X",
            "XXXXXXXXXXXXXXX  XXXXX  X",
            "XXXT XXXXXXXXXX         X",
            "XXX                     X",
            "XXX         XXXXXXXXXXXXX",
            "XXXXXXXXXX  XXXXXXXXXXXXX",
            "XXXXXXXXXX             TX",
            "XXT  XXXXXE             X",
            "XX   XXXXXX        XXXXX",
            "XX    FXXXXXXXXXXX  XXXXX",
            "XX          XXXX        X",
            "XXXXE                   X",
            "XXXXXXXXXXXXXXXXXXXXXXXXX"
        ])  # No auto solution available
        
        return [level_0, level_1, level_2]
    
    def _safe_clear_screen(self):
        """Safely clear the screen without destroying handlers."""
        try:
            # Get all turtles and clear them
            all_turtles = turtle.turtles()[:]
            for t in all_turtles:
                try:
                    t.clear()
                    t.hideturtle()
                except:
                    pass
            # Reset background
            try:
                self.screen.bgcolor(Config.BACKGROUND_COLOR)
            except:
                pass
        except:
            pass
    
    def show_main_menu(self):
        """Display the enhanced main menu with multiple options."""
        # Only clear if already initialized
        if self.screen_initialized:
            self._safe_clear_screen()
        
        self.screen_initialized = True
        self.screen.tracer(0)
        self.buttons.clear()
        
        # Title
        title = turtle.Turtle()
        title.penup()
        title.hideturtle()
        title.color("#F77F00")
        title.goto(0, 250)
        title.write("🎮 LABYRINTH GAME 🎮", align="center", font=("Courier", 32, "bold"))
        
        subtitle = turtle.Turtle()
        subtitle.penup()
        subtitle.hideturtle()
        subtitle.color(Config.COLOR_TEXT)
        subtitle.goto(0, 200)
        subtitle.write("Choose Your Adventure", align="center", font=("Courier", 18, "normal"))
        
        # Menu buttons
        play_button = Button(-150, 50, 300, 60, "▶ PLAY LEVELS")
        play_button.draw()
        self.buttons['play'] = play_button
        
        create_button = Button(-150, -30, 300, 60, "✎ CREATE LEVEL")
        create_button.draw()
        self.buttons['create'] = create_button
        
        select_button = Button(-150, -110, 300, 60, "📋 SELECT LEVEL")
        select_button.draw()
        self.buttons['select'] = select_button
        
        quit_button = Button(-150, -190, 300, 60, "✖ QUIT")
        quit_button.draw()
        self.buttons['quit'] = quit_button
        
        # Instructions
        info = turtle.Turtle()
        info.penup()
        info.hideturtle()
        info.color("gray")
        info.goto(0, -280)
        info.write("Use arrow keys to move | Collect treasures | Avoid enemies", 
                  align="center", font=("Courier", 12, "normal"))
        
        def on_click(x, y):
            if play_button.contains_point(x, y):
                play_button.is_clicked = True
                self.game_mode = 'play'
                self.current_level = 0
            elif create_button.contains_point(x, y):
                create_button.is_clicked = True
                self.game_mode = 'create'
            elif select_button.contains_point(x, y):
                select_button.is_clicked = True
                self.game_mode = 'select'
            elif quit_button.contains_point(x, y):
                quit_button.is_clicked = True
                self._on_close()
        
        self.screen.onclick(on_click)
        self.screen.update()
    
    def setup_level(self, level: GameLevel):
        """Setup a game level."""
        self._safe_clear_screen()
        self.screen.tracer(0)
        
        wall_pen = Wall()
        self.player = Player()
        self.score_display = ScoreDisplay()
        
        # Markers for start/end
        start_marker = turtle.Turtle()
        start_marker.penup()
        start_marker.hideturtle()
        start_marker.shape("square")
        start_marker.color(Config.COLOR_START)
        start_marker.speed(0)
        
        end_marker = turtle.Turtle()
        end_marker.penup()
        end_marker.hideturtle()
        end_marker.shape("square")
        end_marker.color(Config.COLOR_END)
        end_marker.speed(0)
        
        # Parse level
        for row_idx, row in enumerate(level.layout):
            for col_idx, char in enumerate(row):
                pos = level.get_screen_position(row_idx, col_idx)
                
                if char == 'X':
                    wall_pen.goto(*pos)
                    try:
                        wall_pen.shape("wall1.gif")
                    except turtle.TurtleGraphicsError:
                        wall_pen.shape("square")
                    wall_pen.stamp()
                    level.walls.add(pos.to_tuple())
                
                elif char == 'P':
                    level.player_spawn = pos
                    self.player.goto(*pos)
                
                elif char == 'T':
                    treasure = Treasure(*pos)
                    level.treasures.append(treasure)
                    level.treasure_positions.add(pos.to_tuple())
                
                elif char == 'E':
                    enemy = Enemy(*pos)
                    level.enemies.append(enemy)
                
                elif char == 'S':
                    level.start_pos = pos
                    # For custom levels, S is also the player spawn
                    if not level.player_spawn:
                        level.player_spawn = pos
                        self.player.goto(*pos)
                    start_marker.goto(*pos)
                    start_marker.stamp()
                    level.walls.add(pos.to_tuple())
                
                elif char == 'F':
                    level.end_pos = pos
                    end_marker.goto(*pos)
                    end_marker.stamp()
        
        # Setup enemies
        for enemy in level.enemies:
            enemy.set_obstacles(level.walls, level.treasure_positions)
            enemy.set_player(self.player)
            turtle.ontimer(enemy.move, t=250)
        
        # Setup controls
        self._setup_controls(level)
        
        # Add level buttons
        self.auto_mode = False
        self.create_mode = False
        self.return_to_menu = False
        
        # Clear previous buttons
        self.buttons.clear()
        
        # Menu button (always visible)
        menu_button = Button(-600, 200, 120, 50, "MENU")
        menu_button.draw()
        self.buttons['menu'] = menu_button
        
        # Show Auto button only if level has auto_solution, otherwise show Create button
        if level.auto_solution:
            auto_button = Button(-600, 100, 120, 50, "Auto")
            auto_button.draw()
            self.buttons['auto'] = auto_button
        else:
            create_button = Button(-600, 100, 120, 50, "Create")
            create_button.draw()
            self.buttons['create'] = create_button
        
        # Setup click handler for buttons
        def handle_button_click(x, y):
            if self.buttons.get('menu') and self.buttons['menu'].contains_point(x, y):
                self.buttons['menu'].is_clicked = True
                self.return_to_menu = True
            elif self.buttons.get('auto') and self.buttons['auto'].contains_point(x, y):
                self.buttons['auto'].is_clicked = True
                self.auto_mode = True
            elif self.buttons.get('create') and self.buttons['create'].contains_point(x, y):
                self.buttons['create'].is_clicked = True
                self.create_mode = True
        
        self.screen.onclick(handle_button_click)
        
        self.score_display.update(self.player.gold)
        self.screen.update()
    
    def _setup_controls(self, level: GameLevel):
        """Setup keyboard controls."""
        self.screen.listen()
        self.screen.onkey(lambda: self.player.move(Direction.UP, level.walls), "Up")
        self.screen.onkey(lambda: self.player.move(Direction.DOWN, level.walls), "Down")
        self.screen.onkey(lambda: self.player.move(Direction.LEFT, level.walls), "Left")
        self.screen.onkey(lambda: self.player.move(Direction.RIGHT, level.walls), "Right")
    
    def run_auto_mode(self, level: GameLevel):
        """Run auto-solve mode."""
        if not level.auto_solution:
            return
        
        self.player.is_auto_mode = True
        
        # Reset player to spawn position (where 'P' marker is)
        if level.player_spawn:
            self.player.hideturtle()
            self.player.goto(*level.player_spawn)
            self.player.move_history.clear()
            self.player.showturtle()
        
        # Execute solution moves step by step
        for move_str in level.auto_solution:
            self.screen.tracer(0)
            direction = Direction.from_string(move_str)
            
            # Move player
            self.player.move_to_direction(direction)
            
            # Don't collect treasures during auto mode
            
            self.screen.update()
            sleep(0.3)
        
        self.player.is_auto_mode = False
    
    def run_level(self, level: GameLevel) -> bool:
        """Run the game level. Returns True if level completed successfully."""
        self.setup_level(level)
        
        try:
            while True:
                # Check if return to menu
                if self.return_to_menu:
                    self._cleanup_level(level)
                    return False
                
                # Check if create mode was triggered
                if self.create_mode:
                    self._cleanup_level(level)
                    # Set flag to indicate we want creator mode
                    self.game_mode = 'create'
                    return False
                
                # Check if auto button clicked
                if self.auto_mode:
                    self.run_auto_mode(level)
                    self.auto_mode = False
                    # Wait to show the solution
                    sleep(2)
                    # Reset player to start for continued gameplay
                    if level.player_spawn:
                        self.player.goto(*level.player_spawn)
                        self.player.move_history.clear()
                    self.screen.update()
                
                # Check treasure collection
                for treasure in level.treasures[:]:
                    if self.player.is_collision(treasure):
                        self.player.gold += treasure.gold
                        self.score_display.update(self.player.gold)
                        treasure.destroy()
                        level.treasures.remove(treasure)
                
                # Check enemy collision
                for enemy in level.enemies:
                    if self.player.is_collision(enemy):
                        self.player.destroy()
                        self._cleanup_level(level)
                        sleep(1)
                        return False
                
                # Check level completion
                if level.end_pos:
                    end_turtle = turtle.Turtle()
                    end_turtle.penup()
                    end_turtle.hideturtle()
                    end_turtle.goto(*level.end_pos)
                    
                    if self.player.is_collision(end_turtle):
                        # Victory animation - replay moves in reverse
                        self.player.is_reverse_mode = True
                        for direction in self.player.move_history[::-1]:
                            self.screen.tracer(0)
                            self.player.move_to_direction(direction)
                            self.screen.update()
                            sleep(0.2)
                        
                        # Victory message
                        msg = turtle.Turtle()
                        msg.penup()
                        msg.hideturtle()
                        msg.color(Config.COLOR_TEXT)
                        msg.goto(-30, 0)
                        msg.write("Bravo!", font=("Courier", 18, "normal"))
                        self.screen.update()
                        sleep(2)
                        self._cleanup_level(level)
                        return True
                
                # Check if create mode activated during gameplay
                if self.create_mode:
                    self._cleanup_level(level)
                    return False
                
                self.screen.update()
                sleep(0.01)
        except (turtle.Terminator, Exception) as e:
            self._cleanup_level(level)
            return False
    
    def _cleanup_level(self, level: GameLevel):
        """Clean up level resources properly."""
        try:
            # Stop all enemies
            for enemy in level.enemies:
                enemy.is_active = False
                enemy.destroy()
            level.enemies.clear()
            
            # Clear treasures
            for treasure in level.treasures:
                treasure.destroy()
            level.treasures.clear()
        except:
            pass
    
    def run_creator_mode(self):
        """Run the level creator mode with blank canvas."""
        self._safe_clear_screen()
        self.screen.tracer(0)
        
        # Title
        title = turtle.Turtle()
        title.penup()
        title.hideturtle()
        title.color("#F77F00")
        title.goto(0, 400)
        title.write("✎ LEVEL CREATOR", align="center", font=("Courier", 24, "bold"))
        
        # Instructions
        instructions = turtle.Turtle()
        instructions.penup()
        instructions.hideturtle()
        instructions.color(Config.COLOR_TEXT)
        instructions.goto(0, 360)
        instructions.write("Click palette items, then click grid to place", 
                         align="center", font=("Courier", 14, "normal"))
        
        # Draw grid
        self._draw_creator_grid()
        
        # Initialize editor with blank canvas
        self.level_editor = LevelEditor(self.screen, blank=True)
        
        # Setup click handler
        def handle_editor_click(x, y):
            try:
                if self.level_editor:
                    action = self.level_editor.handle_click(x, y)
                    if action == 'play':
                        self._play_custom_level()
                        return
                self.screen.update()
            except Exception:
                pass
        
        self.screen.onclick(handle_editor_click)
        self.screen.update()
        
        # Wait loop - stay in creator until play button is clicked
        while self.game_mode == 'create':
            try:
                self.screen.update()
                sleep(0.1)
            except:
                break
        
        # Wait loop - stay in creator until play button is clicked or game mode changes
        while self.game_mode == 'create':
            try:
                self.screen.update()
                sleep(0.1)
            except:
                break
    
    def _draw_creator_grid(self):
        """Draw grid lines for the creator mode."""
        grid_drawer = turtle.Turtle()
        grid_drawer.penup()
        grid_drawer.hideturtle()
        grid_drawer.speed(0)
        grid_drawer.color("#1a1a1a")
        
        # Calculate grid bounds
        half_width = (Config.GRID_COLS * Config.CELL_SIZE) // 2
        half_height = (Config.GRID_ROWS * Config.CELL_SIZE) // 2
        
        # Draw vertical lines
        for i in range(Config.GRID_COLS + 1):
            x = -half_width + (i * Config.CELL_SIZE)
            grid_drawer.goto(x, half_height)
            grid_drawer.pendown()
            grid_drawer.goto(x, -half_height)
            grid_drawer.penup()
        
        # Draw horizontal lines
        for i in range(Config.GRID_ROWS + 1):
            y = half_height - (i * Config.CELL_SIZE)
            grid_drawer.goto(-half_width, y)
            grid_drawer.pendown()
            grid_drawer.goto(half_width, y)
            grid_drawer.penup()
    
    def _play_custom_level(self):
        """Play the custom created level."""
        if not self.level_editor:
            return
        
        layout = self.level_editor.get_custom_level_layout()
        custom_level = GameLevel(layout)
        
        # Validate level has start and end
        has_start = any('S' in row for row in layout)
        has_end = any('F' in row for row in layout)
        
        if not has_start or not has_end:
            # Show error message
            msg = turtle.Turtle()
            msg.penup()
            msg.hideturtle()
            msg.color("red")
            msg.goto(0, 0)
            msg.write("ERROR: Level needs START (green) and END (red)!", 
                     align="center", font=("Courier", 16, "bold"))
            self.screen.update()
            sleep(2)
            msg.clear()
            self.screen.update()
            return
        
        # Play the level
        self.run_level(custom_level)
        
        # After playing, exit creator mode and return to menu
        self.game_mode = None
    
    def show_level_select(self):
        """Show level selection menu."""
        self._safe_clear_screen()
        self.screen.tracer(0)
        
        # Title
        title = turtle.Turtle()
        title.penup()
        title.hideturtle()
        title.color("#F77F00")
        title.goto(0, 300)
        title.write("📋 SELECT LEVEL", align="center", font=("Courier", 28, "bold"))
        
        # Level buttons
        y_start = 150
        self.buttons.clear()
        for i in range(len(self.levels)):
            level_btn = Button(-200, y_start - (i * 80), 400, 60, f"Level {i + 1}")
            level_btn.draw()
            self.buttons[f'level_{i}'] = level_btn
        
        # Back button
        back_btn = Button(-200, y_start - (len(self.levels) * 80), 400, 60, "← BACK TO MENU")
        back_btn.draw()
        self.buttons['back'] = back_btn
        
        def on_click(x, y):
            for i in range(len(self.levels)):
                if self.buttons[f'level_{i}'].contains_point(x, y):
                    self.buttons[f'level_{i}'].is_clicked = True
                    self.current_level = i
                    self.game_mode = 'play'
                    return
            
            if self.buttons['back'].contains_point(x, y):
                self.buttons['back'].is_clicked = True
                self.game_mode = None
                self.show_main_menu()
        
        self.screen.onclick(on_click)
        self.screen.update()
    
    def run(self):
        """Main game loop with menu system."""
        try:
            self.show_main_menu()
            
            while self.is_running:
                try:
                    if self.game_mode == 'play':
                        # Play through levels
                        while self.current_level < len(self.levels) and self.is_running:
                            level = self.levels[self.current_level]
                            success = self.run_level(level)
                            
                            if not self.is_running:
                                return
                            
                            if self.return_to_menu:
                                self.return_to_menu = False
                                self.game_mode = None
                                self.show_main_menu()
                                break
                            elif self.game_mode == 'create':
                                # Create mode was triggered from within level
                                self.create_mode = False
                                self.run_creator_mode()
                                self.game_mode = None
                                self.show_main_menu()
                                break
                            elif success:
                                self.current_level += 1
                                if self.current_level >= len(self.levels):
                                    # All levels completed
                                    self._show_victory_screen()
                                    self.game_mode = None
                                    self.current_level = 0
                                    self.show_main_menu()
                                    break
                            else:
                                # Level failed, return to menu
                                self.game_mode = None
                                self.show_main_menu()
                                break
                        
                        if self.game_mode == 'play' and self.current_level >= len(self.levels):
                            self.game_mode = None
                            self.show_main_menu()
                            
                    elif self.game_mode == 'create':
                        self.run_creator_mode()
                        self.game_mode = None
                        self.show_main_menu()
                        
                    elif self.game_mode == 'select':
                        self.show_level_select()
                    
                    if self.is_running:
                        self.screen.update()
                        sleep(0.1)
                except turtle.Terminator:
                    # Clean exit when window is closed
                    self.is_running = False
                    exit()
                except Exception as e:
                    if not self.is_running:
                        return
                    # Silently handle errors and return to menu
                    self.game_mode = None
                    try:
                        self.show_main_menu()
                    except:
                        self.is_running = False
                        return
        except (turtle.Terminator, KeyboardInterrupt):
            self.is_running = False
            return
        except Exception as e:
            self.is_running = False
            return
    
    def _show_victory_screen(self):
        """Show victory screen when all levels completed."""
        self._safe_clear_screen()
        self.screen.tracer(0)
        
        # Victory message
        msg = turtle.Turtle()
        msg.penup()
        msg.hideturtle()
        msg.color("#FFD700")
        msg.goto(0, 100)
        msg.write("🎉 CONGRATULATIONS! 🎉", align="center", font=("Courier", 32, "bold"))
        
        msg2 = turtle.Turtle()
        msg2.penup()
        msg2.hideturtle()
        msg2.color(Config.COLOR_TEXT)
        msg2.goto(0, 30)
        msg2.write("You completed all levels!", align="center", font=("Courier", 24, "normal"))
        
        if self.score_display:
            score_msg = turtle.Turtle()
            score_msg.penup()
            score_msg.hideturtle()
            score_msg.color("#F77F00")
            score_msg.goto(0, -30)
            score_msg.write(f"Final Score: {self.score_display.current_score}", 
                          align="center", font=("Courier", 20, "normal"))
        
        # Return button
        return_btn = Button(-150, -150, 300, 60, "← MAIN MENU")
        return_btn.draw()
        
        self.screen.update()
        sleep(3)
        
        def on_click(x, y):
            if return_btn.contains_point(x, y):
                return_btn.is_clicked = True
                self.game_mode = None
        
        self.screen.onclick(on_click)
        
        # Wait for click
        waiting = True
        while waiting and self.game_mode is None:
            try:
                self.screen.update()
                sleep(0.1)
            except:
                break
        
        # Return to menu
        self.show_main_menu()


# ==================== MAIN ====================
def main():
    """Main entry point."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
