# Docker TUI Managers

- cleaner.sh: Nuclear option for when the disk is full. Wipes Docker JSON logs, clears PM2 logs inside containers, and nukes old Nginx .gz rotations.

- manage-backend-containers-gui.py: A terminal interface for app containers. Hit / to search for a container and R to restart. Refreshes every 3 seconds.

- manage-db-gui-tolerance.py: Groups PostGIS and Redis containers by city. If the naming is slightly different, it uses fuzzy matching to pair them up.

- manage-db-gui-indiv.py: A simple list for all DB containers if I just need to check one specific instance.

- UI Logic:

    - Red: Container is dead/exited.

    - White: Container is up.

    - Yellow: It's doing something (starting/restarting).
