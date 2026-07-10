ZONE ?= asia-southeast1-b

.PHONY: judge-up judge-down judge-health judge-ssh

judge-up:
	terraform apply -auto-approve

judge-down:
	terraform destroy -auto-approve

judge-health:
	@echo "Waiting for judge endpoint to become ready..."
	@until curl -sf "$$(terraform output -raw judge_endpoint_url)/health" >/dev/null; do \
		sleep 5; \
	done
	@echo "Ready: $$(terraform output -raw judge_endpoint_url)"

judge-ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
