FROM codercom/code-server:4.99.2

RUN sudo apt update -y && sudo apt install -y python3-distutils python-is-python3 make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

RUN mkdir -p /home/coder/.local/bin
RUN sudo apt install -y python3-pip python3-virtualenv
RUN curl https://pyenv.run | bash
RUN touch /home/coder/.bashrc
RUN echo 'PATH="/home/coder/.local/bin:$PATH"' >> /home/coder/.bashrc
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> /home/coder/.bashrc
RUN echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> /home/coder/.bashrc
RUN echo 'eval "$(pyenv init -)"' >> /home/coder/.bashrc

RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
RUN chmod +x ./kubectl
RUN sudo mv ./kubectl /usr/local/bin/kubectl
