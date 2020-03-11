# to build image, cd to dockerfile directory (repo root directory) and run docker build -t ebay-image .
# to start, run docker run -d --net as-net --ip 172.99.0.14 --restart always --name=ebay-container --mount source=ebay,target=/usr/src/ebay ebay-image

FROM python:3

WORKDIR /var/lib/docker/volumes/ebay

RUN apt-get update -qq

# Install Cron
RUN apt-get update -qq && apt-get install -y cron

# Install VIM
RUN ["apt-get", "install", "-y", "vim"]

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /opt/entrypoint.sh

# Add crontab file in the cron directory
COPY crontab /etc/cron.d/autosearch-cron

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/autosearch-cron

# Create the log file
RUN touch /var/log/cron.log


# Run a bash script on startup so the Python scripts have the environmental
# variables defined in Dockerfile
# https://stackoverflow.com/questions/27771781/how-can-i-access-docker-set-environment-variables-from-a-cron-job

CMD ["/bin/bash", "/opt/entrypoint.sh"]
