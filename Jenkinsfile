pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Backend') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'mvn -B clean verify'
                    } else {
                        bat 'mvn -B clean verify'
                    }
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'target/surefire-reports/*.xml'
                }
            }
        }

        stage('Frontend') {
            steps {
                dir('frontend') {
                    script {
                        if (isUnix()) {
                            sh 'npm ci'
                            sh 'npm run build'
                        } else {
                            bat 'npm ci'
                            bat 'npm run build'
                        }
                    }
                }
            }
        }

        stage('PostgreSQL and application') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker compose config --quiet'
                        sh 'docker compose up -d --build --wait'
                    } else {
                        bat 'docker compose config --quiet'
                        bat 'docker compose up -d --build --wait'
                    }
                }
            }
        }
    }
}