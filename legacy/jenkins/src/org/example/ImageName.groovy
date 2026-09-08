package org.example

// Small helper class used by the shared library. Included so the Jenkinsfile's dependence on
// classes under src/ (which have no GitHub Actions equivalent) shows up in the analyzer output.
class ImageName implements Serializable {
  static String of(String registry, String service, String tag) {
    return "${registry}/${service}:${tag}".toLowerCase()
  }
}
