from pprint import pprint

import argparse
import json
import os.path
import random
import readline
import shlex
import subprocess

from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.messages import ToolMessage
from langchain.tools import tool

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--file", help="File containing the prompt to send")
parser.add_argument("-s", "--system", help="System prompt")
parser.add_argument("-n", "--no-tools", help="Disable tool use", action="store_true")
parser.add_argument("-m", "--model", help="Model to use", default="qwen2.5")
parser.add_argument("prompt", nargs="?")
args = parser.parse_args()

llm = ChatOllama(model=args.model)

#
# Define tools the agent can work with
# 
'''
@tool("ls", description="Gets the list of files in a directory. Use it to know what files are in a directory on the filesystem")
def ls(path):
	if os.path.isdir(path):
		return os.listdir(path)
	elif os.path.isfile(path):
		return [path]
	else:
		raise ValueError("No such file or directory")
'''

@tool("file reader")
def cat(path):
	"""
	Return the contents of the file at path
	"""
	try:
		with open(path) as f:
			return f.read()
	except Exception:
		return ""

@tool("head", description="Read the first lines of the given file (10 by default)")
def head(path, n=10):
	try:
		with open(path) as f:
			lines = []
			for _ in range(n):
				s = f.readline()
				if not s: 
					break
				lines.append(s)
			return "\n".join(lines)
	except Exception:
		return ""

'''
@tool("grep", description="Returns the lines of text that contain the given substring")
def grep(substring, text):
	with open("find_str.debug", "a") as f:
		f.write(f"findstr(<<{substring}>>, <<{text}>>)\n")
	return [line for line in text.split("\n") if substring in line]
'''

@tool("shell", description="Execute a shell command and retrieve the output")
def shell(cmd):
	with open("/tmp/toolcall.sh", "w") as f:
		f.write(cmd)

	p = subprocess.run(shlex.split("/bin/bash /tmp/toolcall.sh"), capture_output=True, timeout=60)
	if p.returncode != 0:
		return f"TOOFAIL {p.stdout}. {p.stderr}"
	try:
		s = p.stdout.decode()
	except UnicodeDecodeError:
		return p.stdout
	return s

class Agent:
	def __init__(self, model, tools=[], system_prompt="You are a helpful agent"):
		# Instantiate agent
		self.agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
		self.memory = []

	def do_slash_command(self, prompt): # {{{1
		if prompt == "/memory":
			for i,message in enumerate(self.memory):
				print(i, message)
		elif prompt.startswith("/memdelete"):
			try:
				_, index = prompt.split(" ")
				index = int(index)
				if 0 <= index < len(self.memory):
					del self.memory[index]
			except Exception:
				...
		elif prompt == "/memclear":
			self.memory = []
		elif prompt == "/memload":
			mempath = "agent_memory.json"
			if os.path.exists(mempath):
				with open(mempath) as f:
					self.memory = json.load(f)
		elif prompt == "/memsave":
			with open("agent_memory.json", "w") as f:
				json.dump(self.memory, f)
		elif prompt in ("/quit", "/exit"):
			return None
		else:
			return prompt

		return ""
	
	def get_user_input(self): # {{{1
		prompt = ""
		while prompt == "" or prompt.startswith("/"):
			prompt = input(">>> \x1b[32m")
			print("\x1b[m", end="")
			prompt = self.do_slash_command(prompt)
			if prompt is None: break

		return prompt
	
	def stream_response(self, prompt): # {{{1
		response = ""
		try:
			#i = max(1, i % 256)
			i = 4
			for chunk in self.agent.stream(
				{"messages": [{"role": "user", "content": prompt}]},
				stream_mode="messages",
				version="v2",
			):
				message = chunk[0]
				for tool_call in getattr(message, "tool_calls", []):
					print(f"\x1b[33mCalling {tool_call['name']}({tool_call['args']})\x1b[m", flush=True)
				if type(message) == ToolMessage:
					print(f"\x1b[35m{message.content[:4096]}\x1b[m")
					self.memory.append(message.content)
				else:
					print(f"\x1b[38;5;{i}m{message.content}\x1b[m", end="", flush=True)
					response += message.content
				with open("agent.error", "a") as f:
					f.write(f"\n\n{chunk[1:]}")
			print()
			self.memory.append(response)
		except KeyboardInterrupt:
			pass

	def run(self, initial_prompt = ""): # {{{1
		prompt = initial_prompt
		if not prompt:
			prompt = self.get_user_input()

		while True:
			if prompt is None:
				break
			self.memory.append(prompt)
			if not prompt.startswith("/"):
				prompt = f"For the context, here are our previous exchanges:\n" + "\n".join(self.memory) + "\n" + prompt
			self.stream_response(prompt)
			prompt = self.get_user_input()

if args.file:
	prompt = open(args.file).read()
elif args.prompt:
	prompt = args.prompt[0]

system_prompt = """You are an expert in everything related to software programming. However, unless explicitely asked: DO NOT generate code.
When asked to generate code, provide very detailed answers. Otherwise be as concise as possible.
You can use the `shell` tool to read files."""

system_prompt = """You are an agent specialized in HR (Human Resources) topics, and French laws related to work."""

system_prompt = """You can use the following shell tools to as needed:
- curl
- wget
- grep
- cat"""

system_prompt = """Tu es Jarvis, mon assistant personnenl. Lorsque je te demande d'effectuer une tâche pour moi, commence par regarder dans le dossier `/root/skills` ; ce dernier contient des fichiers markdown qui expliquent comment effectuer certaines tâches. Chaque fichier comporte un en-tête, avec un nom et une description. Parcours les fichiers un par un, lis l'en-tête du fichier en cours pour déterminer si le fichier est utile pour la tâche à accomplir.  Si c'est le cas, lis-le en intégralité pour avoir la marche à suivre, sinon passe au fichier suivant. Si aucun fichier ne correspond à la tâche à accomplir, fait de ton mieux.
Pour lire l'en-tête des fichiers, tu peux utiliser l'outil `head`, et pour le lire en intégralité, tu peux utiliser l'outil `cat`."""

if args.system:
	system_prompt = args.system
tools = [cat, head] if args.no_tools else [shell]
agent = Agent(llm, tools=tools, system_prompt = system_prompt)
agent.run()
