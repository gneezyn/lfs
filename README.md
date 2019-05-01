PyLFS
=====
**Originally Forked from [mgax/lfs](https://github.com/mgax/lfs)**

A minimal Python implementation of [git-lfs](https://github.com/github/git-lfs). 

[![Build Status](https://travis-ci.org/gneezyn/lfs.svg?branch=master)](https://travis-ci.org/gneezyn/lfs)

## Server Setup

Install [pipenv](https://pipenv.readthedocs.io/#install-pipenv-today)
```
pipenv --three install

git clone https://github.com/gneezyn/lfs.git
cd lfs

mkdir data
git init --bare data/repo.git

cat > settings.py <<EOF
GIT_PROJECT_ROOT = '`pwd`/data'
SERVER_URL = 'http://localhost:5000'
EOF

pipenv install
pipenv run python lfs.py
```
After the first run, the command `pipenv install` should only need to be run if you make any changes to the code. Similarly, `pipenv run python lfs.py` must be run every time you want to start the server.

## Client Setup
Make sure that the server is working before you run the `git push` command.
```
cd ~
git init repo
cd repo
git lfs install
git config -f .lfsconfig lfs.url http://127.0.0.1:5000/repo.git/info/lfs
git lfs track '*.jpg'
curl -O https://rawgit.com/mgax/lfs/master/testsuite/hardwrk.jpg
git add .
git commit -m 'test data'
git remote add origin https://github.com/<username>/repo.git
git push --set-upstream origin master
```

## Configs
`GIT_PROJECT_ROOT` - 
`SERVER_URL` - the URL of the GitLFS Server (e.g., http://localhost:5000, http://example.com)