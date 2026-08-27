#!/usr/bin/env python3.8
import time
from pprint import pprint
from domains import *
import asyncio
import argparse
import sys

async def get_all_responses(timeout=0.1, display=True):
	responses = []
	while True:
		try:
			response = json.loads(await asyncio.wait_for(Session.ws.recv(), timeout=timeout))
			responses.append(response)
			if display:
				print('<<<')
				pprint(response)
				print()
		except asyncio.exceptions.TimeoutError:
			break
	return responses

async def get_response():
	response = None
	try:
		response = json.loads(await asyncio.wait_for(Session.ws.recv(), timeout=0.1))
		print('<<<')
		pprint(response)
		print()
	except asyncio.exceptions.TimeoutError:
		pass
	return response

async def main():
	async with websockets.connect(Session.url) as Session.ws:
		targets = (await Target.getTargets())['result']['targetInfos']
		target = targets[1]
		result = await Target.attachToTarget(target['targetId'])
		await get_all_responses()
		sessionid = result['params']['sessionId']
		Session.sessionid = sessionid
		pprint(result)
		pprint(await Debugger.enable())
		responses = await get_all_responses()
		#pprint(await Debugger.pause())
		for response in responses:
			if response['method'] == 'Debugger.scriptParsed':
				script_id = response['params']['scriptId']
				break

		#pprint(await Debugger.getScriptSource(script_id))

		#pprint(await Debugger.searchInContent(script_id, query='new'))

		possible_bp_response = await Debugger.getPossibleBreakpoints(script_id)
		pprint(possible_bp_response)

		bp_location = possible_bp_response['result']['locations'][0]
		bp_line = bp_location['lineNumber']
		bp_column = bp_location['columnNumber']
		bp_response = await Debugger.setBreakpoint(script_id, bp_line, bp_column)
		pprint(bp_response)

		pprint(await Debugger.setBreakpointsActive(False))
		pprint(await Debugger.setBreakpointsActive())

		pprint(await Debugger.setInstrumentationBreakpoint())

		#await Debugger.pause()
		#_ = await get_all_responses(timeout=5)
		#pprint(_)
		#pprint(await Debugger.stepInto())
		#pprint(await Debugger.stepOut())
		
		pprint(await DOM.enable())
		pprint(await DOM.getDocument())
		pprint(await DOM.describeNode(1))

		await DOM.getNodeForLocation(0, 0)
		_ = await get_all_responses(timeout=3, display=False)
		pprint(_[-1])
		node_id = _[-1]['result']['nodeId']

		_ = await DOM.getOuterHTML(node_id)

		#_ = await DOM.moveTo(node_id, 27)
		#await get_all_responses(display=False)

		_ = await DOM.querySelector(node_id, 'a')
		pprint(_)
		await get_all_responses()

		_ = await DOM.querySelectorAll(node_id, 'a')
		pprint(_)
		await get_all_responses()

		# Disable methods
		pprint(await DOM.disable())
		pprint(await Debugger.disable())

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('url', help="Remote debugging server URL (ws://<host>:<port>/devtools/browser/<uuid>")
	args = parser.parse_args()
	Session.url = args.url
	asyncio.run(main())
