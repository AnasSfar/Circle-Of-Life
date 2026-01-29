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
H_ENERGY = 30         # active threshold
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
PREY_GRASS_GAIN_PER_UNIT = 1       # 1 energy per grass unit
PREDATOR_EAT_GAIN = 40
PREY_MIN_EAT = 1

# Grass dynamics
GRASS_GROWTH_PER_TICK = 50
DROUGHT_GRASS_FACTOR = 0.1         # during drought, growth is reduced

# Decision probabilities
PREY_EAT_PROB = 0.8
PREY_REPRO_PROB = 0.5

PRED_HUNT_PROB = 0.6
PRED_REPRO_PROB = 0.5
