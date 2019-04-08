PyLFS
=====
**Originally Forked from [mgax/lfs](https://github.com/mgax/lfs)**

A minimal Python implementation of [git-lfs](https://github.com/github/git-lfs). 

[![Build Status](https://travis-ci.org/gneezyn/lfs.svg?branch=master)](https://travis-ci.org/gneezyn/lfs)

## Setup

Install [pipenv](https://pipenv.readthedocs.io/#install-pipenv-today)
```
pipenv --three install

mkdir data
git init --bare data/repo.git

git clone https://github.com/gneezyn/lfs.git

cat > lfs/settings.py <<EOF
GIT_PROJECT_ROOT = '`pwd`/data'
SERVER_URL = 'http://localhost:5000'
EOF

cd lfs
pipenv run python lfs.py
```

## Using as remote
```
git init repo
cd repo
git lfs track '*.jpg'
curl -O https://rawgit.com/mgax/lfs/master/testsuite/hardwrk.jpg
git add .
git commit -m 'test data'
git remote add origin http://foo:bar@localhost:5000/repo.git
git push --set-upstream origin master
```