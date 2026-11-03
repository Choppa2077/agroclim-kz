# Jenkins controller for agroclim-kz: Jenkins LTS + plugins + docker CLI + kubectl.
# Users, credentials and the pipeline job are not clicked together in the UI;
# they come from casc.yaml (Configuration as Code) when the container starts.
FROM jenkins/jenkins:2.580.2-lts-jdk21

USER root

# Docker CLI and buildx from Docker's apt repository. The daemon is not here:
# builds run in the docker:dind sidecar defined in docker-compose.yml.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
 && chmod a+r /etc/apt/keyrings/docker.asc \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin \
 && rm -rf /var/lib/apt/lists/*

# kubectl pinned to the cluster version and verified against its published checksum.
ARG KUBECTL_VERSION=v1.37.0
RUN arch="$(dpkg --print-architecture)" \
 && base="https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}" \
 && curl -fsSLo /usr/local/bin/kubectl "${base}/kubectl" \
 && echo "$(curl -fsSL "${base}/kubectl.sha256")  /usr/local/bin/kubectl" | sha256sum --check - \
 && chmod 0755 /usr/local/bin/kubectl

COPY casc.yaml /etc/jenkins/casc.yaml

USER jenkins
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/etc/jenkins/casc.yaml
COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
