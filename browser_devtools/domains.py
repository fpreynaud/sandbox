import websockets
import json

class Session:
	id = 1
	sessionid =  None

class Domain:
	async def send_receive(method, params=None):
		if Session.sessionid is not None:
			msg = {"sessionId":Session.sessionid, "id":Session.id, "method":method}
		else:
			msg = {"id":Session.id, "method":method}
		if params is not None:
			msg['params'] = params
		print('>>>', msg)
		Session.id += 1
		await Session.ws.send(json.dumps(msg))
		response = json.loads(await Session.ws.recv())
		return response

class Browser(Domain):
	description = "Methods and events for browser management"

	async def close():
		"""Close browser gracefully"""
		return await Domain.send_receive("Browser.close")

	async def getVersion():
		"""Return version information"""
		return await Domain.send_receive("Browser.getVersion")

class Debugger(Domain):
	description = "Debugger domain exposes JavaScript debugging capabilities. It allows setting and removing breakpoints, stepping through execution, exploring stack traces, etc."

	async def disable():
		"""Disables debugger for given page."""
		return await Domain.send_receive("Debugger.disable")

	async def enable():
		"""Enables debugger for the given page. Clients should not assume that the debugging has been enabled until the result for this command is received."""
		return await Domain.send_receive("Debugger.enable")

	async def pause():
		"""Stops on the next JavaScript statement."""
		return await Domain.send_receive("Debugger.pause")

	async def getPossibleBreakpoints(script_id, end_line=199):
		"""Returns possible locations for breakpoint. scriptId in start and end range locations should be the same."""
		start_location = ({'scriptId':script_id, 'lineNumber':0})
		end_location = ({'scriptId':script_id, 'lineNumber':end_line})
		return await Domain.send_receive("Debugger.getPossibleBreakpoints", params={'start':start_location, 'end':end_location, 'restrictToFunction':False})
	
	async def getScriptSource(script_id):
		"""Resumes JavaScript execution."""
		return await Domain.send_receive("Debugger.getScriptSource", params={'scriptId':script_id})

	async def resume():
		"""Resumes JavaScript execution."""
		return await Domain.send_receive("Debugger.resume")
	
	async def searchInContent(script_id, query, case_sensitive=False, is_regex=False):
		"""Searches for given string in script content."""
		return await Domain.send_receive("Debugger.searchInContent", params={'scriptId':script_id, 'query':query, 'caseSensitive':case_sensitive, 'isRegex': is_regex})
	
	async def setBreakpoint(script_id, line=0, column=0, condition=''):
		location = {'scriptId':script_id, 'lineNumber':line, 'columnNumber':column}
		return await Domain.send_receive("Debugger.setBreakpoint", params={'location':location, 'condition':condition})
	
	async def setBreakpointsActive(active=True):
		"""Sets instrumentation breakpoint."""
		return await Domain.send_receive("Debugger.setBreakpointsActive", params={'active':active})
	
	async def setInstrumentationBreakpoint(instrumentation='beforeScriptExecution'):
		"""Sets instrumentation breakpoint."""
		return await Domain.send_receive("Debugger.setInstrumentationBreakpoint", params={'instrumentation':instrumentation})
	
	async def setPauseOnExceptions(state='none'):
		"""Defines pause on exceptions state. Can be set to stop on all exceptions, uncaught exceptions, or caught exceptions, no exceptions. Initial pause on exceptions state is none."""
		return await Domain.send_receive("Debugger.setPauseOnExceptions", params={'state':state})
	
	async def stepInto():
		"""Steps into the function call."""
		return await Domain.send_receive("Debugger.stepInto")

	async def stepOut():
		"""Steps out of the function call."""
		return await Domain.send_receive("Debugger.stepOut")

	async def stepOver():
		"""Steps over the statement."""
		return await Domain.send_receive("Debugger.stepOver")

class DOM(Domain):
	async def describeNode(node_id):
		"""Describes node given its id, does not require domain to be enabled. Does not start tracking any objects, can be used for automation."""
		return await Domain.send_receive("DOM.describeNode", params={'nodeId':node_id})

	async def disable():
		"""Disables DOM agent for the given page."""
		return await Domain.send_receive("DOM.disable")
	
	async def enable():
		"""Enables DOM agent for the given page."""
		return await Domain.send_receive("DOM.enable")
	
	async def getDocument(depth=1, pierce=False):
		"""Returns the root DOM node (and optionally the subtree) to the caller. Implicitly enables the DOM domain events for the current target."""
		return await Domain.send_receive("DOM.getDocument", params={'depth':depth, 'pierce':pierce})
	
	async def getNodeForLocation(x, y, include_user_agent_shadow_dom=False, ignore_pointer_events_none=False):
		"""Returns node id at given location. Depending on whether DOM domain is enabled, nodeId is either returned or not."""
		return await Domain.send_receive("DOM.getNodeForLocation", params={'x':x, 'y':y, 'includeUserAgentShadowDOM':include_user_agent_shadow_dom, 'ignorePointerEventsNone': ignore_pointer_events_none})
	
	async def getOuterHTML(node_id):
		"""Returns node's HTML markup."""
		return await Domain.send_receive("DOM.getOuterHTML", params={'nodeId':node_id})
	
	async def highlightNode(node_id):
		"""Highlights DOM node"""
		"""Does not seem to do anything, but no error returned"""
		return await Domain.send_receive("Overlay.highlightNode", params={'nodeId':node_id, 'highlightConfig':{'borderColor':{'r':255, 'g':0, 'b':0, 'a':0}}})
	
	async def moveTo(node_id, target_node_id):
		"""Moves node into the new container, places it before the given anchor."""
		return await Domain.send_receive("DOM.moveTo", params={'nodeId':node_id, 'targetNodeId':target_node_id})
	
	async def querySelector(node_id, selector):
		"""Executes querySelector on a given node"""
		return await Domain.send_receive("DOM.querySelector", params={'nodeId':node_id, 'selector':selector})

	async def querySelectorAll(node_id, selector):
		"""Executes querySelectorAll on a given node"""
		return await Domain.send_receive("DOM.querySelectorAll", params={'nodeId':node_id, 'selector':selector})
class Target(Domain):
	description = "Supports additional targets discovery and allows to attach to them."

	async def getTargets():
		"""Supports additional targets discovery and allows to attach to them."""
		return await Domain.send_receive("Target.getTargets")
	
	async def attachToTarget(target_id):
		"""Attaches to the target with given id."""
		return await Domain.send_receive("Target.attachToTarget", params={"targetId":target_id, "flatten":True})
	


