# Million-Project
Improving the counting flow of the group by checking for errors and missing numnbers.

## 1. Prequisites
Working environment for the services, I used an always-free Oracle Ampre Ubuntu VM.
I created a network and subnet before, than the VM.
It will probably only be available with an PAYGO account, but if configured right should stay free of cost.
```
sudo apt update && sudo apt upgrade -y
sudo mkdir /million-project
```
## 2. Installations
### docker
```
sudo apt install ca-certificates curl gnupg lsb-release -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
```
**verify with:    docker run hello-world**
> To run docker commands without root, run this command then logout:     sudo usermod -aG docker ${USER}
