# Artifact store: one S3 bucket plus an IAM role that can read and write it.
#
# Mirrors infra/crossplane/composition.yaml resource for resource so the two can be compared;
# see docs/terraform-vs-crossplane.md. Nothing in this repo applies it.

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  bucket_name = "${var.name}-${random_id.suffix.hex}"
  tags        = merge(var.tags, { "managed-by" = "terraform", "component" = var.name })
}

# ------------------------------------------------------------------ S3

resource "aws_s3_bucket" "this" {
  bucket = local.bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = var.versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# ------------------------------------------------------------------ IAM

data "aws_iam_policy_document" "assume" {
  dynamic "statement" {
    for_each = length(var.trusted_principal_arns) > 0 ? [1] : []
    content {
      sid     = "TrustedPrincipals"
      effect  = "Allow"
      actions = ["sts:AssumeRole"]

      principals {
        type        = "AWS"
        identifiers = var.trusted_principal_arns
      }
    }
  }

  dynamic "statement" {
    for_each = var.oidc_provider_arn != null ? [1] : []
    content {
      sid     = "GitHubActionsOIDC"
      effect  = "Allow"
      actions = ["sts:AssumeRoleWithWebIdentity"]

      principals {
        type        = "Federated"
        identifiers = [var.oidc_provider_arn]
      }

      condition {
        test     = "StringEquals"
        variable = "token.actions.githubusercontent.com:aud"
        values   = ["sts.amazonaws.com"]
      }

      condition {
        test     = "StringLike"
        variable = "token.actions.githubusercontent.com:sub"
        values   = ["repo:${var.github_repository}:*"]
      }
    }
  }
}

resource "aws_iam_role" "access" {
  name                 = "${var.name}-artifact-store"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  max_session_duration = 3600
  tags                 = local.tags
}

data "aws_iam_policy_document" "access" {
  statement {
    sid       = "ListBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.this.arn]
  }

  statement {
    sid       = "ObjectReadWrite"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["${aws_s3_bucket.this.arn}/*"]
  }
}

resource "aws_iam_policy" "access" {
  name   = "${var.name}-artifact-store"
  policy = data.aws_iam_policy_document.access.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "access" {
  role       = aws_iam_role.access.name
  policy_arn = aws_iam_policy.access.arn
}
