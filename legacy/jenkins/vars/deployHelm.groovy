#!/usr/bin/env groovy
// Shared-library step: helm upgrade --install into the target namespace.
//
// Callers: deployHelm(service: 'orders-api', environment: 'staging', tag: 'abc123')
//
// The credential lookup and the kubeconfig handling are what make this hard to lift-and-shift;
// in GitHub Actions this becomes the `deploy` reusable workflow with an environment-scoped secret.

def call(Map args) {
  def service     = args.service     ?: error('deployHelm: service is required')
  def environment = args.environment ?: error('deployHelm: environment is required')
  def tag         = args.tag         ?: error('deployHelm: tag is required')
  def namespace   = args.namespace   ?: "${service}-${environment}"

  withCredentials([file(credentialsId: "kubeconfig-${environment}", variable: 'KUBECONFIG')]) {
    sh """
      helm upgrade --install ${service} ./charts/${service} \\
        --namespace ${namespace} --create-namespace \\
        --set image.tag=${tag} \\
        --values ./charts/${service}/values-${environment}.yaml \\
        --wait --timeout 10m
    """
  }
}
