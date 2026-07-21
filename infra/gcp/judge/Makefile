ZONE ?= asia-southeast1-b

.PHONY: judge-up judge-down judge-tunnel judge-health judge-ssh

judge-up:
	terraform apply -auto-approve -input=false

judge-down:
	terraform destroy -auto-approve -input=false

judge-tunnel:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE) -- -N -L 8001:127.0.0.1:8000

judge-health:
	@until curl -sf http://127.0.0.1:8001/health >/dev/null; do sleep 5; done
	@echo "Ready: http://127.0.0.1:8001/v1"

judge-ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
