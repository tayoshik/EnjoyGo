import tkinter as tk
from tkinter import messagebox, filedialog
import numpy as np
from enum import Enum
from typing import Set, Tuple, List, Optional, Dict
import json
from datetime import datetime
from collections import defaultdict
import time

class Stone(Enum):
    EMPTY = 0
    BLACK = 1
    WHITE = 2

class GameState(Enum):
    ONGOING = 0
    FINISHED = 1

class GoGame:
    def __init__(self, size: int = 19):
        self.size = size
        self.board = np.zeros((size, size), dtype=int)
        self.current_player = Stone.BLACK
        self.previous_boards = []  # Store multiple previous board states for ko detection
        self.move_history = []
        self.consecutive_passes = 0
        self.state = GameState.ONGOING
        self.captured_stones = {Stone.BLACK: 0, Stone.WHITE: 0}
        self.territory_cache = {}  # Cache for territory calculations
        self.group_cache = {}  # Cache for group calculations
        self.last_move = None

    def clear_caches(self):
        """Clear calculation caches when board state changes"""
        self.territory_cache.clear()
        self.group_cache.clear()

    def get_group_cached(self, point: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """Cached version of get_group for better performance"""
        cache_key = (point, tuple(map(tuple, self.board)))
        if cache_key in self.group_cache:
            return self.group_cache[cache_key]

        x, y = point
        color = self.board[x, y]
        if color == Stone.EMPTY.value:
            return set()

        group = set()
        visited = np.zeros_like(self.board, dtype=bool)
        stack = [(x, y)]
        
        while stack:
            current = stack.pop()
            if visited[current]:
                continue
                
            visited[current] = True
            cx, cy = current
            if self.board[cx, cy] == color:
                group.add(current)
                # Add adjacent points
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    new_x, new_y = cx + dx, cy + dy
                    if (0 <= new_x < self.size and 
                        0 <= new_y < self.size and 
                        not visited[new_x, new_y] and 
                        self.board[new_x, new_y] == color):
                        stack.append((new_x, new_y))

        self.group_cache[cache_key] = group
        return group

    def get_liberties(self, group: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """Get all liberties (empty adjacent points) of the given group"""
        liberties = set()
        visited = set()
        
        for point in group:
            x, y = point
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                new_x, new_y = x + dx, y + dy
                if ((new_x, new_y) not in visited and 
                    0 <= new_x < self.size and 
                    0 <= new_y < self.size):
                    visited.add((new_x, new_y))
                    if self.board[new_x, new_y] == Stone.EMPTY.value:
                        liberties.add((new_x, new_y))
        return liberties

    def make_move(self, point: Tuple[int, int]) -> bool:
        """Make a move at the given point or pass"""
        if self.state == GameState.FINISHED:
            return False

        if point == "pass":
            self.consecutive_passes += 1
            self.move_history.append("pass")
            self.current_player = Stone.WHITE if self.current_player == Stone.BLACK else Stone.BLACK
            
            if self.consecutive_passes >= 2:
                self.state = GameState.FINISHED
            return True

        if not isinstance(point, tuple) or len(point) != 2:
            return False

        x, y = point
        if not (0 <= x < self.size and 0 <= y < self.size):
            return False

        if not self.is_valid_move(point):
            return False

        # Store previous board state
        self.previous_boards.append(self.board.copy())
        if len(self.previous_boards) > 8:  # Keep only last 8 board states
            self.previous_boards.pop(0)

        # Place the stone
        self.board[x, y] = self.current_player.value
        self.consecutive_passes = 0

        # Capture stones
        captured = self.check_capture(point)
        if captured:
            self.captured_stones[self.current_player] += len(captured)
            for cx, cy in captured:
                self.board[cx, cy] = Stone.EMPTY.value

        # Clear caches
        self.clear_caches()

        # Record move
        self.move_history.append(point)
        self.last_move = point

        # Switch players
        self.current_player = Stone.WHITE if self.current_player == Stone.BLACK else Stone.BLACK
        return True

    def is_valid_move(self, point: Tuple[int, int]) -> bool:
        """Check if a move is valid according to all Go rules"""
        if point == "pass":
            return True

        if not isinstance(point, tuple) or len(point) != 2:
            return False

        x, y = point
        if not (0 <= x < self.size and 0 <= y < self.size):
            return False

        # Check if point is empty
        if self.board[x, y] != Stone.EMPTY.value:
            return False

        # Check for ko violation
        if self.is_ko_violation(point):
            return False

        # Temporarily place the stone
        temp_board = self.board.copy()
        self.board[x, y] = self.current_player.value

        # Check for suicide rule
        group = self.get_group_cached(point)
        captured_stones = self.check_capture(point)
        has_liberties = bool(self.get_liberties(group))

        # Revert the temporary stone
        self.board = temp_board

        # The move is valid if either:
        # 1. The group has liberties after placing the stone
        # 2. The move captures enemy stones
        return has_liberties or captured_stones

    def check_capture(self, point: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """Check and return all stones that would be captured by placing a stone at point"""
        captured_stones = set()
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            adj = (point[0] + dx, point[1] + dy)
            if (0 <= adj[0] < self.size and 
                0 <= adj[1] < self.size and 
                self.board[adj[0], adj[1]] == (3 - self.current_player.value)):
                group = self.get_group_cached(adj)
                if not self.get_liberties(group) - {point}:
                    captured_stones.update(group)
        return captured_stones

    def is_ko_violation(self, point: Tuple[int, int]) -> bool:
        """Check if a move would violate the ko rule"""
        if not self.previous_boards:
            return False

        # Temporarily make the move
        temp_board = self.board.copy()
        self.board[point] = self.current_player.value
        
        # Capture any surrounded stones
        captured = self.check_capture(point)
        for cx, cy in captured:
            self.board[cx, cy] = Stone.EMPTY.value

        # Check if this board state has occurred before
        current_state = self.board.tobytes()
        ko_violation = any(prev.tobytes() == current_state for prev in self.previous_boards)

        # Restore the original board
        self.board = temp_board
        return ko_violation

    def get_valid_moves(self) -> List[Tuple[int, int]]:
        """Get all valid moves on the board"""
        valid_moves = []
        for x in range(self.size):
            for y in range(self.size):
                if self.is_valid_move((x, y)):
                    valid_moves.append((x, y))
        return valid_moves

    def calculate_territory(self) -> Dict[Stone, int]:
        """Calculate territory and determine winner"""
        territory = {Stone.BLACK: 0, Stone.WHITE: 0}
        visited = set()

        def flood_fill(point: Tuple[int, int]) -> Tuple[Set[Tuple[int, int]], Optional[Stone]]:
            if point in visited:
                return set(), None
            
            color = None
            territory_points = {point}
            visiting = {point}
            boundary = set()
            
            while visiting:
                current = visiting.pop()
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    adj = (current[0] + dx, current[1] + dy)
                    if adj not in visited and 0 <= adj[0] < self.size and 0 <= adj[1] < self.size:
                        if self.board[adj] == Stone.EMPTY.value:
                            if adj not in territory_points:
                                territory_points.add(adj)
                                visiting.add(adj)
                        else:
                            boundary.add(self.board[adj])
                            
            visited.update(territory_points)
            
            if len(boundary) == 1:
                color = Stone(list(boundary)[0])
                
            return territory_points, color

        # Find all territories
        for i in range(self.size):
            for j in range(self.size):
                if self.board[i, j] == Stone.EMPTY.value and (i, j) not in visited:
                    points, owner = flood_fill((i, j))
                    if owner:
                        territory[owner] += len(points)

        # Add captured stones to territory
        territory[Stone.BLACK] += self.captured_stones[Stone.BLACK]
        territory[Stone.WHITE] += self.captured_stones[Stone.WHITE]

        return territory

class AIPlayer:
    def __init__(self, game, stone_color):
        self.game = game
        self.color = stone_color
        
    def evaluate_position(self, point):
        """評価関数: 特定の位置の価値を評価"""
        score = 0
        x, y = point
        
        # 盤端への評価（中央に近い方が価値が高い）
        center_x = self.game.size // 2
        center_y = self.game.size // 2
        distance_from_center = abs(x - center_x) + abs(y - center_y)
        score -= distance_from_center
        
        # 隣接する空点の数を評価
        liberties = 0
        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
            new_x, new_y = x + dx, y + dy
            if (0 <= new_x < self.game.size and 
                0 <= new_y < self.game.size and 
                self.game.board[new_x, new_y] == Stone.EMPTY.value):
                liberties += 1
        score += liberties * 2
        
        # 敵の石を取れる手には高い評価を与える
        self.game.board[x, y] = self.color.value
        captured = self.game.check_capture((x, y))
        self.game.board[x, y] = Stone.EMPTY.value
        score += len(captured) * 10
        
        return score
        
    def get_move(self):
        """最適な手を選択"""
        best_score = float('-inf')
        best_move = None
        available_moves = []
        
        # 全ての合法手を評価
        for x in range(self.game.size):
            for y in range(self.game.size):
                point = (x, y)
                if self.game.is_valid_move(point):
                    score = self.evaluate_position(point)
                    available_moves.append((score, point))
        
        # スコアでソートして上位の手から選択
        if available_moves:
            available_moves.sort(reverse=True)
            # ランダム性を持たせるため、上位3手からランダムに選択
            from random import choice
            return choice(available_moves[:3])[1]
        
        # 打てる手がない場合はパス
        return "pass"








   
class GoGameGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Go Game")
        self.game = GoGame()
        self.ai_player = None
        self.vs_computer = False
                
        # Configure grid
        self.cell_size = 30
        self.margin = 20
        self.canvas_size = self.cell_size * self.game.size + 2 * self.margin
        
        # Create widgets
        self.create_widgets()
        
        # Bind events
        self.canvas.bind('<Button-1>', self.on_click)
        # AIモード選択ボタンを追加
        tk.Button(self.info_frame, text="vs Computer (Black)", 
                 command=lambda: self.start_vs_computer(True)).pack()
        tk.Button(self.info_frame, text="vs Computer (White)", 
                 command=lambda: self.start_vs_computer(False)).pack()
                
    def create_widgets(self):
        # Create main frame
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(padx=10, pady=10)
        
        # Create canvas
        self.canvas = tk.Canvas(
            self.main_frame, 
            width=self.canvas_size, 
            height=self.canvas_size,
            bg='#DDBB33'  # Traditional go board color
        )
        self.canvas.pack(side=tk.LEFT)
        
        # Create info frame
        self.info_frame = tk.Frame(self.main_frame)
        self.info_frame.pack(side=tk.LEFT, padx=10)
        
        # Add labels and buttons
        self.turn_label = tk.Label(self.info_frame, text="Black's turn")
        self.turn_label.pack()
        
        self.captured_label = tk.Label(self.info_frame, text="Captured stones:\nBlack: 0\nWhite: 0")
        self.captured_label.pack(pady=10)
        
        tk.Button(self.info_frame, text="Pass", command=self.pass_move).pack()
        tk.Button(self.info_frame, text="Save Game", command=self.save_game).pack()
        tk.Button(self.info_frame, text="Load Game", command=self.load_game).pack()
        
        self.draw_board()
        
    def draw_board(self):
        """Draw the go board with stones"""
        self.canvas.delete("all")
        
        # Draw grid lines
        for i in range(self.game.size):
            # Horizontal lines
            self.canvas.create_line(
                self.margin, self.margin + i * self.cell_size,
                self.canvas_size - self.margin, self.margin + i * self.cell_size
            )
            # Vertical lines
            self.canvas.create_line(
                self.margin + i * self.cell_size, self.margin,
                self.margin + i * self.cell_size, self.canvas_size - self.margin
            )
        
        # Draw star points (for 19x19 board)
        if self.game.size == 19:
            star_points = [(3, 3), (3, 9), (3, 15),
                          (9, 3), (9, 9), (9, 15),
                          (15, 3), (15, 9), (15, 15)]
            for x, y in star_points:
                self.draw_star_point(x, y)
        
        # Draw stones
        for i in range(self.game.size):
            for j in range(self.game.size):
                if self.game.board[i, j] != Stone.EMPTY.value:
                    self.draw_stone(i, j, self.game.board[i, j])
                    
        # Highlight last move
        if self.game.last_move and self.game.last_move != "pass":
            x, y = self.game.last_move
            self.draw_last_move_marker(x, y)
        
    def draw_stone(self, row, col, color):
        """Draw a stone at the specified position"""
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        radius = self.cell_size // 2 - 2
        
        stone_color = "black" if color == Stone.BLACK.value else "white"
        self.canvas.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill=stone_color,
            outline="black" if color == Stone.WHITE.value else ""
        )
        
    def draw_star_point(self, row, col):
        """Draw a star point at the specified position"""
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        radius = 3
        self.canvas.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill="black"
        )
        
    def draw_last_move_marker(self, row, col):
        """Draw a marker for the last move"""
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        radius = 3
        color = "white" if self.game.board[row, col] == Stone.BLACK.value else "black"
        self.canvas.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill=color
        )
        
    def get_board_position(self, event):
        """Convert canvas coordinates to board position"""
        x = event.x - self.margin + self.cell_size // 2
        y = event.y - self.margin + self.cell_size // 2
        row = y // self.cell_size
        col = x // self.cell_size
        
        if 0 <= row < self.game.size and 0 <= col < self.game.size:
            return row, col
        return None
        
    def on_click(self, event):
        """Handle mouse clicks on the board"""
        pos = self.get_board_position(event)
        if pos and self.game.state == GameState.ONGOING:
            if self.game.make_move(pos):
                self.update_display()
                
    def pass_move(self):
        """Handle pass move"""
        if self.game.state == GameState.ONGOING:
            self.game.make_move("pass")
            self.update_display()
            
            if self.game.state == GameState.FINISHED:
                self.show_game_result()
                
    def update_display(self):
        """Update the display after a move"""
        self.draw_board()
        self.turn_label.config(
            text="White's turn" if self.game.current_player == Stone.WHITE else "Black's turn"
        )
        self.captured_label.config(
            text=f"Captured stones:\nBlack: {self.game.captured_stones[Stone.BLACK]}\n"
                 f"White: {self.game.captured_stones[Stone.WHITE]}"
        )
        
    def show_game_result(self):
        """Show the game result when the game is finished"""
        territory = self.game.calculate_territory()
        result_text = (
            f"Game Over!\n\n"
            f"Black territory: {territory[Stone.BLACK]}\n"
            f"White territory: {territory[Stone.WHITE]}\n\n"
            f"{'Black' if territory[Stone.BLACK] > territory[Stone.WHITE] else 'White'} "
            f"wins by {abs(territory[Stone.BLACK] - territory[Stone.WHITE])} points!"
        )
        messagebox.showinfo("Game Result", result_text)
        
    def save_game(self):
        """Save the current game"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".sgf",
            filetypes=[("SGF files", "*.sgf"), ("All files", "*.*")]
        )
        if filename:
            self.game.save_sgf(filename)
            messagebox.showinfo("Success", "Game saved successfully!")
            
    def load_game(self):
        """Load a saved game"""
        filename = filedialog.askopenfilename(
            filetypes=[("SGF files", "*.sgf"), ("All files", "*.*")]
        )
        if filename:
            # Implementation of SGF loading would go here
            pass
    def start_vs_computer(self, player_is_black):
        """コンピューター対戦を開始"""
        self.game = GoGame()  # 新しいゲームを開始
        self.vs_computer = True
        ai_color = Stone.WHITE if player_is_black else Stone.BLACK
        self.ai_player = AIPlayer(self.game, ai_color)
        
        # AIが黒の場合、最初の手を打つ
        if not player_is_black:
            self.ai_make_move()
            
        self.update_display()
        
    def ai_make_move(self):
        """AIの手を実行"""
        if self.game.state == GameState.ONGOING:
            move = self.ai_player.get_move()
            if self.game.make_move(move):
                self.update_display()
                if move == "pass":
                    messagebox.showinfo("AI Move", "AI passed")
                    
    def on_click(self, event):
        """クリックイベントハンドラーを更新"""
        if self.game.state == GameState.ONGOING:
            pos = self.get_board_position(event)
            if pos and self.game.make_move(pos):
                self.update_display()
                
                # プレイヤーの手の後でAIの手を実行
                if self.vs_computer and self.game.state == GameState.ONGOING:
                    self.master.after(500, self.ai_make_move)  # 少し遅延を入れる
                    
    def pass_move(self):
        """パス機能を更新"""
        if self.game.state == GameState.ONGOING:
            self.game.make_move("pass")
            self.update_display()
            
            # プレイヤーのパスの後でAIの手を実行
            if self.vs_computer and self.game.state == GameState.ONGOING:
                self.master.after(500, self.ai_make_move)
            
            if self.game.state == GameState.FINISHED:
                self.show_game_result()

if __name__ == "__main__":
    root = tk.Tk()
    app = GoGameGUI(root)
    root.mainloop()
    
