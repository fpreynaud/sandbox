import sys
import os
import tty
import random
from termios import *

IFLAGS = 0
OFLAGS = 1
CFLAGS = 2
LFLAGS = 3
ISPEED = 4
OSPEED = 5
CC = 6

f = sys.stdout.write
g = open('/tmp/out.txt', 'w')
mode = tcgetattr(sys.stdin)
attrs = mode.copy()

# Enter raw mode for stdin
mode[LFLAGS] = mode[LFLAGS] & ~(ICANON | ECHO)
tcsetattr(sys.stdin, TCSAFLUSH, mode)

# Switch to alternate screen
# Enable mouse tracking (any-event)
# Enable extended coordinates
f('\x1b[?1049h\x1b[?1003h\x1b[?1006h')
sys.stdout.flush()
i = 0
sign = 1

MOUSE_DOWN = False
MOUSE_LEFT = 0
MOUSE_MIDDLE = 1
MOUSE_RIGHT = 2
MOUSE_BUTTON = None

# Escape sequence format for mouse tracking
# ESC [ <&lt;> <bouton> ; <colonne> ; <ligne> <m|M> 
# <bouton> : Encoded on 1 bytes. First 2 low bits tell which button was pressed, the 3 next tell the modifier (ctrl/alt/shift), and the last ones are 0. Examples:
#	00000 : left click
#	00001 : middle click
#	00010 : right click
#	00100 : shift + left click
#	01001 : meta/alt + middle click
#	10010 : ctrl + right click
# M for button pressed, and m for button released
def get_click():
	global i, sign, MOUSE_DOWN, MOUSE_RELEASE
	seq = b''
	with open('/dev/stdin', 'rb') as s:
		c = s.read(1)
		seq += c
		while c != b'M' and c != b'm':
			c = s.read(1)
			seq += c

	MOUSE_DOWN = (seq[-1:] == b'M')
	seq = seq[3:-1]
	button, column, row = seq.split(b';')
	modifiers = []

	if int(button) & 3 == MOUSE_RIGHT:
		mb = 'mb3'
		MOUSE_BUTTON = MOUSE_RIGHT
	elif int(button) & 3 == MOUSE_MIDDLE:
		mb = 'mb2'
		MOUSE_BUTTON = MOUSE_MIDDLE
	elif int(button) & 3 == MOUSE_LEFT:
		mb = 'mb1'
		MOUSE_BUTTON = MOUSE_LEFT
	else:
		mb = 'mb0'
		MOUSE_DOWN = False
		MOUSE_BUTTON = None

	if int(button) & 4 == 4:
		modifiers.append('shift')
	if int(button) & 8 == 8:
		modifiers.append('alt')
	if int(button) & 16 == 16:
		modifiers.append('ctrl')

	if  MOUSE_DOWN:
		if MOUSE_BUTTON == MOUSE_LEFT:
			cell = f'\x1b[{int(row.decode())};{int(column.decode())}H\x1b[48;2;255;0;0m \x1b[m'
		elif MOUSE_BUTTON == MOUSE_RIGHT:
			cell = f'\x1b[{int(row.decode())};{int(column.decode())}H\x1b[48;2;0;255;0m \x1b[m'
		else:
			cell = f'\x1b[{int(row.decode())};{int(column.decode())}H\x1b[48;2;0;0;255m \x1b[m'
		f(cell)
		g.write(cell)
		i += sign
		if i >= 255:
			sign = -1
		if i < 0:
			i = 0
			sign = 1

	sys.stdout.flush()

for _ in range(30000):
	try:
		get_click()
	except KeyboardInterrupt:
		break
g.close()

# Restore terminal attributes
tcsetattr(sys.stdin, TCSAFLUSH, attrs)

# Disable mouse tracking
# Exit alternate screen
f('\x1b[?1002l\x1b[?1003l\x1b[?1005l\x1b[?1015l\x1b[?1006l\x1b[?1049l')
