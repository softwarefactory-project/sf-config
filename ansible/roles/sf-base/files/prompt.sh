prompt='#'
if [ "$(id -u)" != "0" ]; then
    prompt='$'
fi
PS1="[\u@$(hostname -f) \W]${prompt} "
