# config.py

# Simulation timing
import random


TICK_DURATION = 1  # second

# Environment
ENV_HOST = "127.0.0.1"
ENV_PORT = 5001
WEB_PORT = 8001


# Limits
MAX_PREYS = 200
MAX_PREDATORS = 80
MAX_GRASS = 5000

# Initial state
INITIAL_GRASS = 2000

# Energy thresholds
H_ENERGY = 30         # hungry/active threshold
R_ENERGY = 60         # reproduction threshold

# Energy dynamics
PREY_INITIAL_ENERGY = random.randint(30, 60)
PREDATOR_INITIAL_ENERGY = random.randint(30, 60)

PREY_ENERGY_DECAY = 2
PREDATOR_ENERGY_DECAY = 1

# Reproduction energy cost
PREY_REPRO_COST = 15
PRED_REPRO_COST = 20

# Food gains
PREY_GRASS_GAIN_PER_UNIT = 0.25       # 0.25 energy per grass unit
PREDATOR_EAT_GAIN = 40

# Grass dynamics
GRASS_GROWTH_PER_TICK = 50
DROUGHT_GRASS_FACTOR = 0.1         # during drought, growth is reduced

# Decision probabilities
PREY_EAT_PROB = 0.8
PREY_REPRO_PROB = 0.5

PRED_HUNT_PROB = 0.6
PRED_REPRO_PROB = 0.5

# Prey eating request bounds
PREY_MIN_EAT = 1
PREY_MAX_EAT_FACTOR = 2   # requested max = int(R_ENERGY * factor)

# Drought scheduling (env self-timer)
ENABLE_DROUGHT_TIMER = False
DROUGHT_TIMER_EVERY_SEC = 15

DROUGHT_MIN_SECONDS = 8
DROUGHT_MAX_SECONDS = 18
NORMAL_MIN_SECONDS = 10
NORMAL_MAX_SECONDS = 25
