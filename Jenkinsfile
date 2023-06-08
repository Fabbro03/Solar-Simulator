pipeline {
  agent any
  options {
    buildDiscarder(logRotator(numToKeepStr: '5'))
  }
  stages {
    stage('Build') {
      dockerImage = docker.build("fabbro03/solar-simulator:latest")
    }
    stage('Push image') {
        withDockerRegistry([ credentialsId: "dockerhub", url: "" ]) {
        dockerImage.push()
        }
    }    
  }
  post {
    always {
      sh 'docker logout'
    }
  }
}