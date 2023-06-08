#Deriving the latest base image
FROM python:latest


#Labels as key value pair
LABEL Maintainer="Fabbro03"


# Any working directory can be chosen as per choice like '/' or '/home' etc
# i have chosen /usr/app/src
WORKDIR /

#to COPY the remote file at working directory in container
COPY Energy_sim.py ./
# Now the structure looks like this '/usr/app/src/test.py'


#CMD instruction should be used to run the software
#contained by your image, along with any arguments.
RUN pip install paho-mqtt
CMD [ "python", "./Energy_sim.py"]