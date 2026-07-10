ZONE ?= asia-southeast1-b
BUCKET ?= $(shell terraform output -raw project_id 2>/dev/null)-ai-experiments-model-cache

.PHONY: up down backup

up:
	terraform apply -auto-approve

down:
	terraform destroy -auto-approve

backup:
	@echo "Snapshotting argilla Postgres to GCS..."
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE) -- \
	  "docker exec argilla-postgres-1 pg_dump -U argilla argilla | gzip" \
	  | gsutil cp - "gs://$(BUCKET)/argilla-backups/backup-$$(date +%Y%m%d-%H%M%S).sql.gz"
	@echo "Backup complete."
