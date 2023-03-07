FROM codercom/code-server:4.8.3

RUN sudo apt update -y && sudo apt install -y python3-distutils python-is-python3 python3-virtualenv make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3
RUN python3 -m pip install poetry
RUN curl https://pyenv.run | bash
RUN echo 'PATH="/home/coder/.local/bin:$PATH"' > ~/.bashrc
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
RUN echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
RUN echo 'eval "$(pyenv init -)"' >> ~/.bashrc
