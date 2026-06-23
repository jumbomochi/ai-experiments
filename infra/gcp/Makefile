ZONE ?= asia-southeast1-b

.PHONY: up down health ssh

up:
	terraform apply -auto-approve

down:
	terraform destroy -auto-approve

health:
	@echo "Waiting for vLLM endpoint to become ready..."
	@until curl -sf "$$(terraform output -raw endpoint_url)/health" >/dev/null; do \
		sleep 5; \
	done
	@echo "Ready: $$(terraform output -raw endpoint_url)"

ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
