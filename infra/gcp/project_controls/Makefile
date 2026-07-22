include ../project.env

export TF_VAR_project_id=$(GCP_PROJECT_ID)

.PHONY: guard init validate plan apply

guard:
	cd ../../.. && uv run python -m shared.gcp.config --file infra/gcp/project.env --check-gcloud

init: guard
	terraform init -reconfigure \
		-backend-config="bucket=$(GCP_STATE_BUCKET)" \
		-backend-config="prefix=project-controls"

validate: guard
	terraform validate

plan: guard
	terraform plan -input=false

apply: guard
	terraform apply -input=false
