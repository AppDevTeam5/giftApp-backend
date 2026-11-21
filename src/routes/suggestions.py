"""
LLM gift and event suggestions.  Owner: TBD

Planned routes:
  POST /api/suggestions/gifts/    {person_id or user_id, occasion} -> list of gift ideas within budget
  POST /api/suggestions/events/   {event_id} -> theme, food and activity ideas based on the guests

Steps for each route: gather the data from the database -> build the prompt ->
call the LLM (key from LLM_API_KEY in .env) -> check the JSON it returns -> respond.
Handle timeouts and errors with a 503 instead of crashing.
"""

from flask import Blueprint

suggestions_bp = Blueprint("suggestions", __name__)
