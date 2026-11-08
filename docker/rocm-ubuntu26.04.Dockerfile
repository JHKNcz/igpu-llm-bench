# Archived ROCm build recipe for the Radeon 890M (gfx1150).
#
# This is the Dockerfile found in the source tree. It is not proven to be the
# exact image used for the archived runs; the original container image ID is
# recorded in docs/hardware.md. The comments were translated to English; the
# commands are unchanged.

# 1. Clean Ubuntu 26.04 base
FROM ubuntu:26.04

# 2. Avoid interactive prompts during installation (e.g. timezone selection)
ENV DEBIAN_FRONTEND=noninteractive

# 3. Install prerequisites for Docker and additional libraries (per AMD documentation)
RUN apt-get update && apt-get install -y \
    sudo wget gpg perl \
    libatomic1 libquadmath0 \
    git cmake build-essential

# 4. Download and import the GPG key
RUN mkdir --parents --mode=0755 /etc/apt/keyrings && \
    wget https://stable.repo.amd.com/rocm/gpg/packages.gpg -O - | \
    gpg --dearmor | tee /etc/apt/keyrings/amdrocm.gpg > /dev/null

# 5. Create a deb822 repository (corrected syntax for Podman)
RUN printf "X-Repo-Id: amdrocm-stable\n\
Types: deb\n\
URIs: https://stable.repo.amd.com/rocm/core/packages/ubuntu2604/\n\
Suites: stable\n\
Components: main\n\
Architectures: amd64\n\
Signed-By: /etc/apt/keyrings/amdrocm.gpg\n\
Enabled: yes\n" > /etc/apt/sources.list.d/amdrocm-stable.sources

# 6. Install the exact ROCm 10.0.0 development package for the Radeon 890M (gfx1150)
#    (This package contains the compilers, CMake configuration, and headers for llama.cpp.)
RUN apt-get update && apt-get install -y \
    amdrocm-core-dev10.0-gfx1150

WORKDIR /LLM
