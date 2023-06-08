import pygame
import time
import random

# Inisialisasi Pygame
pygame.init()

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

# Permainan berjalan
game_over = False

# Loop utama
while not game_over:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_over = True
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

    # Update layar
    pygame.display.update()

    # Mengecek jika snake makan makanan
    if snake_x == food_x and snake_y == food_y:
        food_x = round(random.randrange(0, screen_width - snake_block_size) / 20.0) * 20.0
        food_y = round(random.randrange(0, screen_height - snake_block_size) / 20.0) * 20.0
        snake_length += 1

    # Kecepatan permainan
    clock = pygame.time.Clock()
    clock.tick(snake_speed)

# Berakhirnya permainan
pygame.quit()
quit()
