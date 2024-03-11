#! /bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# This is intended to be a customizable entrypoint for each language, it has to be generic enough
(
  cd ${SCRIPT_DIR}/../typescript && \
  rm -rf ${SCRIPT_DIR}/../typescript/dist && \
  npm install && \
  npm run clean && \
  npm run build
)
