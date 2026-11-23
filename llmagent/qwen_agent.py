from dataclasses import dataclass
from shutil import get_terminal_size
from typing import List, Dict
import argparse
import json
import os
import re
import readline
import requests
import shlex
import subprocess
import time
from uuid import uuid4

def hex_to_ansi(color: str, background=False):
	color = color.lstrip("#").strip()
	plane = 48 if background else 38
	if (len(color) != 6
	    or any((c not in "abcdef0123456789" for c in color.lower()))):
		return "\x1b[m"
	r, g, b = int(color[:2], 16), int(color[2:4], 16), int(color[4:], 16)
	return f"\x1b[{plane};2;{r};{g};{b}m"
	
RESET = "\x1b[m"
THINK_COLOR = hex_to_ansi("ffa0a0")
RESPONSE_COLOR = hex_to_ansi("ffff9b")
DEBUG_COLOR = hex_to_ansi("646494")
CODEBLOCK_COLOR = hex_to_ansi("665544", True) + hex_to_ansi("ff6681")
NOT_STARTED = 0
STARTED = 1
DONE = 2
system_prompt = """You are a helpful assistant."""
tools = [
	{
		"name": "ls", 
		"description": "Calls the ls shell command", 
		"parameters": {
			"type": "object", "required": [], 
			"properties": {
				"path": {"type": "string", "description": "The file of folder to call ls on"}
			}
		}
	},
	{ 
		"name": "read_file",
		"description": "Read a file on the disk, totally or partially",
		"parameters": {
			"type": "object", "required": ["path"],
			"properties": {
				"path": {"type": "string", "description": "The file to read"},
				"start": {"type": "int", "description": "The first line of the file to read. Defaults to 1."},
				"end": {"type": "int", "description": "The last line of the file to read. Defaults to -1, which means read until end of file."}
			}
		}
	},
	{
		"name": "write_file",
		"description": "Write data to a file on the disk",
		"parameters": {
			"type": "object", "required": ["data", "path"],
			"properties": {
				"data": {"type": "string or bytes", "description": "The data to write"},
				"path": {"type": "string", "description": "The path to the file to which the data is written, relative to the current folder"},
				"append": {"type": "boolean", "description": "If true, append to the file instead of overwriting it"}
			}
		}
	},

	{
		"name": "rm",
		"description": "Remove a file or folder on the filesystem",
		"parameters": {
			"type": "object", "required": ["path"],
			"properties": {
				"path": {"type": "string", "description": "The file or folder to remove"}
			}
		}
	},

	{
		"name": "shell",
		"description": "Execute an arbitrary shell command",
		"parameters": {
			"type": "object", "required": ["cmd"],
			"properties": {
				"path": {"type": "string", "description": "The shell command to run"}
			}
		}
	},
]
messages = []

def ls(path: str) -> str:
	return os.popen(f"ls {path}").read()

def read_file(path: str, start: int = 1, end: int = -1) -> str:
	with open(path) as f:
		lines = f.readlines()
	if start <= 0:
		start = 1
	if end < start:
		end = len(lines)
	
	content = lines[start - 1:end]
	content = "".join(content)

	return content

def write_file(data: str | bytes, path: str, append: bool = False) -> str:
	mode = "a" if append else "w"
	folder = os.path.dirname(path)
	folder = os.path.abspath(folder)
	folder = os.path.relpath(folder)
	folder = folder.lstrip("./")
	if folder:
		os.popen(f"mkdir -p -v {folder}")
	file = os.path.basename(path)
	sanitized_path = os.path.join(folder, file)

	try:
		with open(sanitized_path, mode) as f:
			f.write(data)
	except Exception as e:
		print(f"write_file failed : {e}")
		return f"write_file failed : {e}"
	
	return f"Data successfully written to {path}"

def rm(path: str) -> str:
	return os.popen(f"rm -ri {path}").read()

def shell(cmd: str) -> str:
	p = subprocess.run(cmd, capture_output=True, shell=True, executable="/bin/bash", stderr=subprocess.STDOUT)
	return p.stdout

def default_tool(*args, **kwargs) -> str:
	return ""

def query_ollama(prompt, model="qwen3:5",	max_tokens=8192):
	response = requests.post(
		"http://localhost:11434/api/generate",
		json={
			"model": model,
			"prompt": prompt,
			"options": {"temperature": 0, "num_predict": max_tokens, "think": False},
			"raw": True,
			"think": False
		},
		stream=True
	)
	for line in response.iter_lines():
		yield line


@dataclass
class ParsingState:
	thinking: int = NOT_STARTED
	in_code_block: bool = False
	
def format_content(content, state):
	if content == "<think>" and state.thinking == NOT_STARTED:
		state.thinking = STARTED
		return THINK_COLOR

	if content == "</think>" and state.thinking == STARTED:
		state.thinking = DONE
		return THINK_COLOR

	if state.thinking == STARTED:
		return THINK_COLOR
	
	if content.startswith("```"):
		state.in_code_block = not state.in_code_block
		return CODEBLOCK_COLOR
	
	if state.in_code_block:
		return CODEBLOCK_COLOR
	
	return RESET + RESPONSE_COLOR
	
def stream_response(full_prompt, model="qwen3.5"):
	state = ParsingState()
	thinking_state = NOT_STARTED
	response_started = False
	in_code_block = False
	output = ""
	token_stream = query_ollama(prompt=full_prompt, model=model)
	for response in token_stream:
		data = response.decode()
		print(data, file=open("qwen_debug_logs", "a"))
		data = json.loads(data)
		content = data["response"]
		fmt = format_content(content, state)
		print(fmt + content, end="", flush=True)
		output += content

	if data["done"] and data["done_reason"] == "length":
		output += stream_response(full_prompt + output, model=model)
	return output

def build_prompt(messages=[], tools=[]):
	prompt = ""
	if not messages:
		messages = [Message(role="system", content="You are a helpful assistant")]
	if messages[0].role != "system":
		raise ValueError("First message must be system prompt")
	
	system_message = messages[0]
	if tools:
		content = "# Tools\n\nYou have access to the following functions:\n\n<tools>"
		for tool in tools:
			content += "\n" + json.dumps(tool)
		content += "</tools>"
		content += "\n\nIf you choose to call a function ONLY reply in the following format with NO suffix:\n\n<tool_call>\n<function=example_function_name>\n<parameter=example_parameter_1>\nvalue_1\n</parameter>\n<parameter=example_parameter_2>\nThis is the value for the second parameter\nthat can span\nmultiple lines\n</parameter>\n</function>\n</tool_call>\n\n<IMPORTANT>\nReminder:\n- Function calls MUST follow the specified format: an inner <function=...></function> block must be nested within <tool_call></tool_call> XML tags\n- Required parameters MUST be specified\n- You may provide optional reasoning for your function call in natural language BEFORE the function call, but NOT after\n- If there is no function call available, answer the question like normal with your current knowledge and do not tell the user about function calls\n</IMPORTANT>"
		system_message = Message(role="system", content=content + messages[0].content)

	prompt += f"{system_message}"
	for i, message in enumerate(messages[1:]):
		if message.role == "system":
			continue
		if message.role == "user":
			prompt += f"\n" + message
		elif message.role == "assistant":
			if type(message.reasoning_content) == str:
				reasoning_content = message.reasoning_content
			elif "</think>" in message.content:
				reasoning_content = message.content.split('</think>')[0].rstrip('\n').split('<think>')[-1].lstrip('\n')		
				message.content = message.content.split('</think>')[-1].lstrip('\n')
			if message.tool_calls:
				for tool_call in message.tool_calls:
					prompt += f"\n<tool_call>\n<function={tool_call.tool_name}>\n"
					for arg, value in tool_call.tool_kwargs.items():
						prompt += f"<parameter={arg}>\n{value}\n</parameter>\n"
			prompt += "\n" + message
		elif message.role == "tool":
			if messages[i].role != "tool":
				prompt += "<|im_start|>user"
			prompt += "\n<tool_response>\n"
			prompt += message.content
			prompt += "\n</tool_response>\n"
			if (i + 1) == len(messages) - 1 or ((i + 1) != len(messages) - 1 and messages[i+1].role != "tool"):
				prompt += "<|im_end|>\n"
	return prompt

TOOLS_MAP = { "ls": ls, "write_file": write_file, "shell": shell, "rm": rm, "read_file": read_file}

class Message:
	def __init__(self, role, content, tool_calls=[]):
		self.role = role
		self.content = content
		self.reasoning_content = None
		self.tool_calls = tool_calls
	
	def __repr__(self):
		return f"<|im_start|>{self.role}\n{self.content}<|im_end|>"
	
	def __add__(self, s: str):
		return repr(self) + s
	
	def __radd__(self, s: str):
		return s + repr(self)
	
	def as_dict(self):
		return {"role": self.role, "content": self.content, "reasoning_content": self.reasoning_content}

@dataclass
class ToolCall:
	tool_kwargs: dict
	prefix: str = ""
	suffix: str = ""
	tool_name: str = ""

def parse_tool_calls(output):
	result = None
	tool_calls = []
	while "<tool_call>" in output:
		prefix, tool_call = output.split("<tool_call>", maxsplit=1)
		tool_call, suffix = tool_call.split("</tool_call>", maxsplit=1)

		lines = tool_call.strip().split("\n")
		tool_name = lines[0].split("=")[1].split(">")[0]
		tool_kwargs = {}
		param_name = ""
		param_value = ""
		for line in lines[1:]:
			if line.startswith("<parameter="):
				param_name = line[len("<parameter="):-1]
			elif line == "</parameter>":
				if param_value.endswith("\n"):
					param_value = param_value[:-1]
				tool_kwargs[param_name] = param_value
				param_name = ""
				param_value = ""
			else:
				param_value += line + "\n"
		output = suffix
		tool_calls.append(ToolCall(prefix=prefix, suffix=suffix, tool_name=tool_name, tool_kwargs=tool_kwargs))
	
	for i,tool_call in enumerate(tool_calls):
		if "<tool_call>" in tool_call.suffix:
			tool_calls[i].suffix = tool_calls[i+1].prefix
			
	return tool_calls

def ask_agent(prompt: str, context=""):
	prompt = build_prompt(messages=messages, tools=tools)
	print(DEBUG_COLOR + prompt.split("<|im_start|>user", maxsplit=1)[1] + "\x1b[m", flush=True)
	output = stream_response(prompt)
	output = output.split("</think>", maxsplit=1)
	try:
		output = output[1]
	except IndexError:
		output = output[0]
	
	tool_calls = []
	# Parse tool calls
	if "<tool_call>" in output:
		tool_calls = parse_tool_calls(output)
	
	messages.append(Message(role="assistant", tool_calls=tool_calls, content=output))

	for tool_call in tool_calls:
		try:
			tool_output = tool_proxy(TOOLS_MAP.get(tool_call.tool_name, default_tool))(**tool_call.tool_kwargs)
		except Exception as e:
			tool_output = f"An error occured running tool {tool_call.tool_name}. Error details: {e}"

		messages.append(Message(role="tool", content=tool_output))

	if tool_calls:
		return ""
	return "done"

def ask_permission(f):
	def wrapper(*args, **kwargs):
		permission = input(f"\n{f.__name__} is marked as potentially dangerous. Execute {f.__name__}({args}, {kwargs}) ? ")
		print(permission)
		if permission.lower() in ("y", "yes"):
			return f(*args, **kwargs)
		return "User denied permission to run the tool"
	wrapper.__name__ = f.__name__
	wrapper.__qualname__ = f.__qualname__
	return wrapper
		
def tool_proxy(tool_func):
	dangerous = [rm, shell]
	if tool_func in dangerous:
		return ask_permission(tool_func)
	return tool_func
		
def prompt_user():
	prompt = input("\n\x1b[m>>> ")
	while prompt.endswith("\\"):
		prompt = prompt[:-1] + "\n"
		prompt += input("\x1b[m... ")
	return prompt

def manage_memory():
	while True:
		for i, message in enumerate(messages):
			snippet = message.content.split("\n")[0][:128]
			print(f"{i+1}) {message.role}: {snippet}")
		msg_id = -1
		while msg_id not in range(len(messages)):
			msg_id = input("Select the message you want to view: ")
			if msg_id.lower() == "q":
				return

			try:
				msg_id = int(msg_id) - 1
			except Exception:
				print(f"Error: enter a number between 1 and {len(messages)} ")

		options = ["view", "edit", "delete", "cancel"]
		for i, option in enumerate(options):
			print(f"{i+1}) {option}")

		choice = -1
		while choice not in range(len(options)):
			choice = input("What to do with this message ?")
			try:
				choice = int(choice) - 1
			except Exception:
				pass
		action = options[choice]
		if action == "view":
			print(messages[msg_id].content)
		elif action == "edit":
			with open("/tmp/agent_edit_msg", "w") as f:
				f.write(messages[msg_id].content)
			editor = os.getenv("VISUAL",
					 os.getenv("EDITOR", "vim"))
			p = subprocess.run([editor, "/tmp/agent_edit_msg"])
			if p.returncode != 0:
				print("An error occured while trying to edit the message")
			else:
				with open("/tmp/agent_edit_msg") as f:
					messages[msg_id].content = f.read().strip()
		elif action == "delete":
			del messages[msg_id]
		else:
			continue

if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("-c", "--chat", help="JSON file containing the conversation to load", type=str)
	args = p.parse_args()

	readline.read_history_file()
	try:
		readline.set_history_length(1000)
		if args.chat:
			conv_file = args.chat
		else:
			conv_uuid = str(uuid4())
			conv_file = f"{conv_uuid}.json"

		if os.path.isfile(conv_file):
			messages = [Message(m["role"], m["content"]) 
						for m in json.load(open(conv_file))]
			for message in messages:
				if message.role != "user":
					print(RESPONSE_COLOR, end="")
				print(message.content + "\x1b[m")
		else:
			messages.append(Message(role="system", content=system_prompt))

		prompt = prompt_user()

		while prompt != "/quit":
			if prompt == "/memory":
				manage_memory()
				prompt = prompt_user()
				continue

			if prompt != "":
				messages.append(Message(role="user", content=prompt))
			try:
				prompt = ask_agent(prompt)
			except KeyboardInterrupt:
				prompt = prompt_user()
				continue
			if prompt == "done":
				notif = f"Agent answered: {messages[-1].content[:32]}"
				# Send a desktop notification. May not work on all terminals
				print(f"\x1b]9;{notif}\a", end="")

				# Poor man's notification : open a shell
				#os.popen(f"kitty --hold fish -c 'echo {notif}'")
				prompt = prompt_user()
	finally:
		readline.write_history_file()
		chat_history = [m.as_dict() for m in messages if m.content != "/quit"]
		json.dump(chat_history, open(conv_file, "w"), indent=1)
		print(f"Conversation saved to {conv_file}")
