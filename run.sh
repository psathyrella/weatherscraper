
# weatherscraper:
# while :; do ./upload-forecast.sh; sleep 6h; done

# wrfparser
# ./wrfparser/wrfparser.py --outdir psathyrella.github.io/wrfparser # --no-sleep

# remove history to save disk space NOTE moved this to upload.sh
# cd psathyrella.github.io
# git checkout --orphan tmp-branch
# git add --all wrfparser/  # Add all files and commit them
# git commit -m"new branch"
# git branch -D master  # Deletes the master branch
# git branch -m master  # Rename the current branch to master
# git push -f origin master  # Force push master branch to github
# git gc --aggressive --prune=all     # remove the old files
# # huh, this didn't actually reduce the size of .git/ until I rm -rf'd I
# # rm -rf .git
# # move existing files to a backup probably here, or just delete 'em
# # git init
# # git remote add origin git@github.com:psathyrella/psathyrella.github.io
# # git pull origin master
