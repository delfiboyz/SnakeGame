import pygame
import time
import random

# Inisialisasi Pygame
pygame.init()

# Font waktu
time_font = pygame.font.SysFont(None, 30)
start_time = time.time()

# Warna
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# Lebar dan tinggi layar
screen_width = 800
screen_height = 400

# Inisialisasi layar
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('Snake Game')

# Kecepatan snake
snake_speed = 15

# Ukuran dan posisi awal snake
snake_block_size = 20
snake_block = []
snake_length = 1

# Inisialisasi posisi awal snake
snake_x = screen_width // 2
snake_y = screen_height // 2
snake_block.append((snake_x, snake_y))

# Perubahan posisi snake
x_change = 0
y_change = 0

# Makanan
food_x = round(random.randrange(0, screen_width - snake_block_size) / 20.0) * 20.0
food_y = round(random.randrange(0, screen_height - snake_block_size) / 20.0) * 20.0

# Skor
score = 0

# Font skor
font_style = pygame.font.SysFont(None, 30)

# Font game over
game_over_font = pygame.font.SysFont(None, 48)

# Fungsi untuk menampilkan pesan "Game Over"
def show_game_over_screen():
    game_over_text = game_over_font.render("Game Over", True, RED)
    play_again_text = font_style.render("Press SPACE to Play Again", True, WHITE)
    screen.blit(game_over_text, (screen_width // 2 - game_over_text.get_width() // 2, screen_height // 2 - game_over_text.get_height() // 2))
    screen.blit(play_again_text, (screen_width // 2 - play_again_text.get_width() // 2, screen_height // 2 + game_over_text.get_height() // 2))
    pygame.display.update()
    elapsed_time = round(time.time() - start_time)
    time_text = font_style.render("Time: " + str(elapsed_time) + "s", True, WHITE)
    screen.blit(time_text, (10, 40))
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    waiting = False
                    play_again()

# Fungsi untuk memulai permainan kembali
def play_again():
    global snake_x, snake_y, snake_block, snake_length, x_change, y_change, score, game_over
    snake_block.clear()
    snake_length = 1
    snake_x = screen_width // 2
    snake_y = screen_height // 2
    snake_block.append((snake_x, snake_y))
    x_change = 0
    y_change = 0
    score = 0
    game_over = False

# Permainan berjalan
game_over = False

# Loop utama
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            quit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                x_change = -snake_block_size
                y_change = 0
            elif event.key == pygame.K_RIGHT:
                x_change = snake_block_size
                y_change = 0
            elif event.key == pygame.K_UP:
                y_change = -snake_block_size
                x_change = 0
            elif event.key == pygame.K_DOWN:
                y_change = snake_block_size
                x_change = 0

    # Perubahan posisi snake
    snake_x += x_change
    snake_y += y_change

    # Batasan layar
    if snake_x >= screen_width or snake_x < 0 or snake_y >= screen_height or snake_y < 0:
        game_over = True

    # Makanan
    screen.fill(BLACK)
    pygame.draw.rect(screen, GREEN, [food_x, food_y, snake_block_size, snake_block_size])
    snake_head = (snake_x, snake_y)
    snake_block.append(snake_head)

    if len(snake_block) > snake_length:
        del snake_block[0]

    # Mengecek tabrakan dengan tubuh snake
    for segment in snake_block[:-1]:
        if segment == snake_head:
            game_over = True

    # Menggambar snake
    for segment in snake_block:
        pygame.draw.rect(screen, BLUE, [segment[0], segment[1], snake_block_size, snake_block_size])

    # Menampilkan skor
    score_text = font_style.render("Score: " + str(score), True, WHITE)
    screen.blit(score_text, (10, 10))
    
    # Menampilkan waktu
    elapsed_time = round(time.time() - start_time)
    time_text = time_font.render("Time: " + str(elapsed_time) + "s", True, WHITE)
    screen.blit(time_text, (10, 40))

    # Update layar
    pygame.display.update()

    # Mengecek jika snake makan makanan
    if snake_x == food_x and snake_y == food_y:
        food_x = round(random.randrange(0, screen_width - snake_block_size) / 20.0) * 20.0
        food_y = round(random.randrange(0, screen_height - snake_block_size) / 20.0) * 20.0
        snake_length += 1
        score += 1

    # Kecepatan permainan
    clock = pygame.time.Clock()
    clock.tick(snake_speed)

    # Mengecek jika game over
    if game_over:
        elapsed_time = round(time.time() - start_time)
        score_text = font_style.render("Score: " + str(score), True, WHITE)
        time_text = font_style.render("Time: " + str(elapsed_time) + "s", True, WHITE)
        screen.blit(score_text, (10, 10))
        screen.blit(time_text, (10, 40))
        show_game_over_screen()
        play_again()
