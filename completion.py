import glob
import os.path
import readline

def path_completer(text, state):
	results = glob.glob(glob.escape(os.path.expanduser(text)) + "*")
	results = [r + "/" if os.path.isdir(r) else r for r in results]
	if results == [glob.escape(os.path.expanduser(text))]:
		return None

	return results[state] if len(results) > state else None

delims = readline.get_completer_delims()
readline.set_completer_delims(' \t\n')
readline.parse_and_bind('tab: complete')
readline.set_completer(path_completer)
input()
