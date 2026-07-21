ZONE ?= asia-southeast1-b

.PHONY: up down tunnel health ssh

up:
	terraform apply -auto-approve -input=false

down:
	terraform destroy -auto-approve -input=false

tunnel:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE) -- -N -L 8000:127.0.0.1:8000

health:
	@until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 5; done
	@echo "Ready: http://127.0.0.1:8000/v1"

ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
