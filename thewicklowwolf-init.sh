#!/bin/sh

printf "\033[1;Samaze123\033[0m"
printf "\033[1;34mLidify\033[0m"
echo "Initializing app..."

cat << 'EOF'
_____________________________________

               .-'''''-.             
             .'         `.           
            :             :          
           :               :         
           :      _/|      :         
            :   =/_/      :          
             `._/ |     .'           
          (   /  ,|...-'             
           \_/^\/||__                
       _/~  `""~`"` \_               
     __/  -'/  `-._ `\_\__           
    /    /-'`  `\   \  \-.\          
_____________________________________
Brought to you by Samaze123
_____________________________________

If you'd like to buy me a coffee:
https://buymeacoffee.com/Samaze123

EOF

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "-----------------"
printf "\033[1mRunning with:\033[0m"
echo "PUID=${PUID}"
echo "PGID=${PGID}"
echo "-----------------"

# Create the required directories with the correct permissions
echo "Setting up directories.."
mkdir -p /lidify/config
chown -R "${PUID}":"${PGID}" /lidify

# Start the application with the specified user permissions
echo "Running Lidify..."
exec su-exec "${PUID}":"${PGID}" gunicorn src.Lidify:app -c gunicorn_config.py
