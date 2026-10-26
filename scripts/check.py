"""Stop the deploy if the crawl came back suspiciously small (Drive unreachable, folder made private)."""
import json, sys
docs = json.load(open(sys.argv[1]))
print(len(docs), 'documents')
if len(docs) < 100:
    sys.exit('Too few documents found; keeping the previous site online.')
