import random

def random_string(length):
	return "".join([random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(length)])