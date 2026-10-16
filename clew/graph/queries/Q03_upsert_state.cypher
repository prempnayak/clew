// Q03 upsert_state
// Purpose: after every navigation. Tells the explorer whether the page is new, whether it has been read,
//          and its previous candidate list (to spot elements a release added to a known page).
// Params: $key, $route, $auth, $fingerprint, $name, $url, $agent, $elements (JSON string), $entry, $now
// Callers: clew/explorer/worker.py
MERGE (s:State {key: $key})
  ON CREATE SET s.route = $route, s.auth = $auth, s.fingerprint = $fingerprint, s.name = $name,
                s.url_example = $url, s.first_seen = $now, s.first_seen_by = $agent,
                s.importance = 0.0, s.visits = 0, s.read = false, s.entry = false
WITH s, s.elements AS previous_elements
SET s.visits = s.visits + 1, s.last_seen = $now, s.elements = $elements,
    s.entry = s.entry OR $entry
RETURN s.key AS key, s.first_seen = $now AS is_new, s.read AS read, s.name AS name, previous_elements
