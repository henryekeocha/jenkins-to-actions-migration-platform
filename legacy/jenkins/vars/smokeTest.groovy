#!/usr/bin/env groovy
// Shared-library step: poll a health endpoint until it returns 200 or we give up.
//
// Callers: smokeTest(url: 'https://staging.example.com/orders-api/healthz')

def call(Map args) {
  def url      = args.url      ?: error('smokeTest: url is required')
  def attempts = args.attempts ?: 12
  def delay    = args.delay    ?: 10

  retry(attempts) {
    sleep(time: delay, unit: 'SECONDS')
    sh "curl --fail --silent --show-error --max-time 10 ${url}"
  }
}
