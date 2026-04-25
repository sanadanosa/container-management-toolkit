# Docker TUI Managers

- manage-backend.py: A terminal interface for app containers. Hit / to search for a city and R to restart. Refreshes every 3 seconds so I don't have to.

- manage-db-pairs.py: Groups PostGIS and Redis containers by city. If the naming is slightly different, it uses fuzzy matching to pair them up so I can see if the whole "site" is healthy.

- manage-db-solo.py: A simple list for all DB containers if I just need to check one specific instance.

- UI Logic:

    - Red: Container is dead/exited.

    - White: Container is fine (easier on the eyes than bright green).

    - Yellow: It's doing something (starting/restarting).
