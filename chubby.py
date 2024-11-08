import pygame
from pygame.locals import *
import random
import smbus
import time
import RPi.GPIO as GPIO
import numpy as np

# Initialize Pygame
pygame.init()

clock = pygame.time.Clock()
fps = 120

screen_width = 864
screen_height = 936
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('Chubby Cat')

# Define colors and font
white = (255, 255, 255)
font = pygame.font.SysFont('Bauhaus 93', 60)

# Game variables
# 1. Scrolling part
ground_scroll = 0
scroll_speed = 4
background_scroll = 0
# 2. Game process tracking
flying = False
game_over = False
# 3. Obstacle
tower_gap = 300
tower_frequency = 10000
last_tower = pygame.time.get_ticks() - tower_frequency
# 4. Scoring
score = 0
scored_towers = set()

# Load images
bg = pygame.image.load('/home/user/game/img/bg.PNG')
ground_img = pygame.image.load('/home/user/game/img/ground.PNG')
button_img = pygame.image.load('/home/user/game/img/restart.png')

# GPIO pin setting
# 1. 7-segments LED (segments[0] and segments[1] are a-f for tens and ones respectively)
segments = [[10, 9, 25, 24, 23, 22, 27],[19, 26, 20, 16, 12, 13, 6]]
# 2. Digit control of 7-segments LED (tens and ones)
digit_pins = [8,21]
# 3. Buzzer
BUZZER_PIN = 4
# 4. Switch
SWITCH_PIN = 17
# 5. LED
LED_PIN = 18
# 6. MPU-6050
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
ACCEL_YOUT_H = 0x3D
ACCEL_YOUT_L = 0x3E
MPU6050_LSBG = 16384.0

# Segment configurations for displaying digits 0-9
digit_segments = [
    [1, 1, 1, 1, 1, 1, 0],  # 0 
    [0, 1, 1, 0, 0, 0, 0],  # 1
    [1, 1, 0, 1, 1, 0, 1],  # 2
    [1, 1, 1, 1, 0, 0, 1],  # 3
    [0, 1, 1, 0, 0, 1, 1],  # 4
    [1, 0, 1, 1, 0, 1, 1],  # 5
    [1, 0, 1, 1, 1, 1, 1],  # 6
    [1, 1, 1, 0, 0, 0, 0],  # 7
    [1, 1, 1, 1, 1, 1, 1],  # 8
    [1, 1, 1, 1, 0, 1, 1]   # 9
]

GPIO.setmode(GPIO.BCM)

# Setup all segment and digit control pins as output
for pin in segments:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

for pin in digit_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

# Setup buzzer as output with initial state low
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(BUZZER_PIN, GPIO.LOW)

# Setup LED as output with initial state low
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

# Setup switch as input
GPIO.setup(SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Initialize the I2C bus
bus = smbus.SMBus(1)
bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0)

# Callback function for button press
def handle_button_press(channel):
    global flying, game_over
    if game_over:
        game_over = False
        reset_game()
        flying = False
        GPIO.output(BUZZER_PIN, GPIO.LOW)  # Turn off the buzzer
    elif not flying:
        flying = True

# Setup interrupt for button press
GPIO.add_event_detect(SWITCH_PIN, GPIO.RISING, callback=handle_button_press, bouncetime=200)

# Function to draw text on screen play
def draw_text(text, font, text_col, x, y):
    img = font.render(text, True, text_col)
    screen.blit(img, (x, y))
    
# Function to read accelerometer data form gyro and get combined Y-axis value
def combine_register_values(high, low):
    value = (high << 8) | low
    return -((65535 - value) + 1) if value >= 0x8000 else value

# Function to get accelerometer data
def get_accel_y():
    accel_y = combine_register_values(bus.read_byte_data(MPU6050_ADDR, ACCEL_YOUT_H),
                                      bus.read_byte_data(MPU6050_ADDR, ACCEL_YOUT_L))
    return accel_y / MPU6050_LSBG
    
# Function to display a digit on the 7-segment display
def display_digit(digit,sm,value):
    GPIO.output(digit, 1)  # Turn on the selected digit display
    for i in range(7):
        GPIO.output(sm[i], digit_segments[value][i])  # Set segments for the digit
    time.sleep(0.005)  # Short delay to allow the digit to be visible
    GPIO.output(digit, 0)  # Turn off the digit display

# Function to reset game variables when restarting
def reset_game():
    tower_group.empty()
    chubby.rect.x = screen_width // 2
    chubby.rect.y = 680
    chubby.vel = 0
    scored_towers.clear()
    return 0  # Reset score

# Define the Cat (player character) class
class Cat(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.images = [] # List to store animation frames
        self.index = 0 # Track animation frame
        self.counter = 0
        self.target_width, self.target_height = 115, 80 # Size of character
            
        # Load normal animation frames
        for num in range(1, 4):
            img = pygame.image.load(f"/home/user/game/img/cat{num}.PNG")
            scaled_img = pygame.transform.scale(img, (self.target_width, self.target_height))
            self.images.append(scaled_img)
        
        # Load jump images
        self.jump_image = pygame.image.load("/home/user/game/img/jump.PNG")
        self.jump_image = pygame.transform.scale(self.jump_image, (self.target_width, self.target_height))
        
        # Load death image
        self.died_image = pygame.image.load("/home/user/game/img/died.PNG")
        self.died_image = pygame.transform.scale(self.died_image, (self.target_width, self.target_height))
        
        # Set initial image
        self.image = self.images[self.index]
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        
        # Set initial state of character
        self.vel = 0 # velocity
        self.clicked = False
        self.should_animate = False # animation state
        self.is_jumping = False
        self.jump_timer = 0 # timer for jump animation

    # Function to update cat character while game is not over
    def update(self):
        global flying, game_over
        self.should_animate = False

        if flying and not game_over:
            # Apply gravity to make cat fallind down after jump
            self.vel += 0.5
            if self.vel > 8:
                self.vel = 8
            if self.rect.bottom < 768:
                self.rect.y += int(self.vel)

        if game_over:
            # Show died image when game is over
            self.image = self.died_image
            return  # Exit the update method early

        if not game_over and flying:
            # Check for switch pressing (jump)
            if GPIO.input(SWITCH_PIN) == GPIO.HIGH and not self.clicked:
                self.clicked = True
                GPIO.output(LED_PIN, GPIO.LOW)
                self.vel = -10  # Jump velocity
                self.rect.y -= 10 # Move up
                flying = True
                self.should_animate = True
                self.is_jumping = True
                self.jump_timer = 15 # Set timer for jump
                self.image = self.jump_image
            if GPIO.input(SWITCH_PIN) == GPIO.LOW:
                self.clicked = False

            # Update jump timer and reset jumping state
            if self.is_jumping:
                self.jump_timer -= 1
                if self.jump_timer <= 0:
                    self.is_jumping = False

            if abs(get_accel_y()) > 0:
                self.should_animate = True

            # Only animate if there's user input and not jumping
            if self.should_animate and not self.is_jumping:
                flap_cooldown = 5
                self.counter += 1

                if self.counter > flap_cooldown:
                    self.counter = 0
                    self.index += 1
                    if self.index >= len(self.images):
                        self.index = 0 
                    self.image = self.images[self.index]

        # Update image based on state if not game over
        if not self.is_jumping and not game_over:
            self.image = self.images[self.index]

# Define the Tower class
class Tower(pygame.sprite.Sprite):
    def __init__(self, x, y, position):
        pygame.sprite.Sprite.__init__(self)
        
         # Set the position of the tower: top or bottom based on `position`
        if position == 1:
            # Top tower: randomly choose between tower1 and tower4
            tower_num = random.choice([1, 4]) 
            self.image = pygame.image.load(f"/home/user/game/img/tower{tower_num}.PNG")
            self.image = pygame.transform.flip(self.image, False, True)
            self.rect = self.image.get_rect()
            self.rect.bottomleft = [x, y - int(tower_gap / 2)]
        elif position == -1:
            # Bottom tower: randomly choose between tower1, tower2, and tower3
            tower_num = random.choice([1, 2, 3])  
            self.image = pygame.image.load(f"/home/user/game/img/tower{tower_num}.PNG")
            self.rect = self.image.get_rect()
            self.rect.topleft = [x, y + int(tower_gap / 2)]
            
        self.passed = False  # Add a flag to track if this tower has been passed

    # Function to update tower while game is not over
    def update(self):
        # Move towers left
        self.rect.x -= scroll_speed
        # Remove tower when it goes off screen
        if self.rect.right < 0:
            self.kill()

# Define the Restart Button class
class Button():
    def __init__(self, x, y, image):
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)

    # Function to show restart stage
    def draw(self):
        action = False
        # Restart game when press switch
        if GPIO.input(SWITCH_PIN) == GPIO.HIGH:
            action = True
        screen.blit(self.image, (self.rect.x, self.rect.y))
        return action
        
# Create sprite groups for the player and towers
tower_group = pygame.sprite.Group()
cat_group = pygame.sprite.Group()
chubby = Cat(screen_width // 2, 700)
cat_group.add(chubby)

# Define restart stage
button = Button(screen_width // 2 - 50, screen_height // 2 - 100, button_img)

# Main game loop
run = True
while run:
    clock.tick(fps) # Maintain frame rate

    # Event handling for quitting the game
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

    # Check for button press to start the game
    if GPIO.input(SWITCH_PIN) == GPIO.HIGH and not flying and not game_over:
        flying = True

    # Game controls and logic
    if flying and not game_over:
        accel_y = get_accel_y()
        if accel_y < -0.1:  # Threshold for left movement
            background_scroll += scroll_speed
            # SIMD-like operation using NumPy to move towers
            tower_positions = np.array([tower.rect.x for tower in tower_group.sprites()])
            tower_positions += scroll_speed
            for tower, new_x in zip(tower_group, tower_positions):
                tower.rect.x = new_x
            ground_scroll += scroll_speed
        elif accel_y > 0.1:  # Threshold for right movement and increase speed
            background_scroll -= (scroll_speed*accel_y*5)
            # SIMD-like operation using NumPy to move towers
            tower_positions = np.array([tower.rect.x for tower in tower_group.sprites()])
            tower_positions -= scroll_speed
            for tower, new_x in zip(tower_group, tower_positions):
                tower.rect.x = new_x
            ground_scroll -= scroll_speed

    # Background and ground scroll handling
    if background_scroll > 0:
        background_scroll = -screen_width
    if background_scroll < -screen_width:
        background_scroll = 0
    if ground_scroll > screen_width:
        ground_scroll = 0
    if ground_scroll < -screen_width:
        ground_scroll = 0

    # Draw background
    screen.blit(bg, (background_scroll, 0))
    screen.blit(bg, (background_scroll + screen_width, 0))

    # Update cat if flying
    if flying:
        cat_group.update()

    # Draw towers and cat
    tower_group.draw(screen)
    cat_group.draw(screen)

    # Draw ground
    for i in range(-1, 3):
        screen.blit(ground_img, (ground_scroll + (i * screen_width), 768))

    # Tower generation logic
    if flying and not game_over:
        time_now = pygame.time.get_ticks()
        if time_now - last_tower > tower_frequency:
            tower_height = random.randint(-100, 100)
            btm_tower = Tower(screen_width, screen_height // 2 + tower_height, -1)
            top_tower = Tower(screen_width, screen_height // 2 + tower_height, 1)
            tower_group.add(btm_tower)
            tower_group.add(top_tower)
            last_tower = time_now
        tower_group.update()

        # Scoring logic
        for tower in tower_group:
            if tower.rect.right < chubby.rect.left and not tower.passed:
                if tower not in scored_towers:
                    score += 0.5
                    tower.passed = True
                    GPIO.output(LED_PIN, GPIO.HIGH)
                    scored_towers.add(tower)

    # Check for collision and game over
    if pygame.sprite.groupcollide(cat_group, tower_group, False, False) or chubby.rect.top < 0:
        game_over = True
        GPIO.output(BUZZER_PIN, GPIO.HIGH)  # Turn on the buzzer

    # Restart game if button is pressed
    if game_over and button.draw():
        game_over = False
        score = reset_game()
        flying = False
        GPIO.output(BUZZER_PIN, GPIO.LOW)  # Turn off the buzzer

    # Display score
    draw_text(str(int(score)), font, white, int(screen_width / 2), 20)
    display_digit(digit_pins[0], segments[0], int(score)//10)
    display_digit(digit_pins[1], segments[1], int(score)%10)   # Display on the second digit
    pygame.display.update()

# Clean up GPIO and quit
GPIO.cleanup()
pygame.quit()
