# PDF review
A collaborative PDF review tool

[![.github/workflows/tests.yml](https://github.com/lexbailey/pdfreview/actions/workflows/tests.yml/badge.svg)](https://github.com/lexbailey/pdfreview/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/lexbailey/pdfreview/branch/dev/graph/badge.svg?token=UJLSWC3CNJ)](https://codecov.io/gh/lexbailey/pdfreview)
[![CodeFactor](https://www.codefactor.io/repository/github/lexbailey/pdfreview/badge?s=688975796222516560189bbdcd7e0b81c18f8a79)](https://www.codefactor.io/repository/github/lexbailey/pdfreview)

This tool allows end users to upload PDF documents and share comments
relating to specific aspects. This is a bit like the comment system
used by common PDF viewers, but designed to be hosted centrally and
easy to access.

It aims to offer a number of features:
- Easy for users to create new reviews
- Scalable to large numbers of comments
- Export comments back into PDF for archival
- RSS feeds of comments
- Available offline

## Installation
The source for this is written in python, so should be hosted in a web
environment capable of executing python, along with all necessary python
dependencies. A python virtual environment can also be used.

Care should be taken to ensure subfolders are not browsable, since these
are designed to store all reviews currently ongoing on the system.

## Configuration
Configuration is done by way of a configuration file, config.py.
Since this varies from one installation to the next, this should be
configured according to each specific case.

In particular, paths to required tools such as ghostscript should be
specified, along with a dedicated authentication interface to identify
users.

An example configuration is provided in config.py.sample

## Current status
The tool is currently functional and is ready to be used. There are a
number of limitations that are currently being worked on. See the issues
list for more details.

