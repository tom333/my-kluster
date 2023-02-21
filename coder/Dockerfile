FROM codercom/code-server:latest

RUN sudo apt update -y && sudo apt install -y python python3-distutils python3-pip python3-virtualenv make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
RUN python3 -m pip install poetry
RUN curl https://pyenv.run | bash
RUN echo 'PATH="/home/coder/.local/bin:$PATH"' > ~/.bashrc
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
RUN echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
RUN echo 'eval "$(pyenv init -)"' >> ~/.bashrc
