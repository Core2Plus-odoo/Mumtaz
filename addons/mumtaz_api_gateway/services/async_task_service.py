def enqueue_job(env, tenant, job_type, payload):
    return env["mumtaz.async.job"].create({
        "name": f"{job_type} job",
        "tenant_id": tenant.id,
        "job_type": job_type,
        "payload_json": str(payload or {}),
    })
