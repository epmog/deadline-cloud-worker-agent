# Installer for the AWS Deadline Cloud Worker Agent

# options:
#   -h, --help            show this help message and exit
#   --farm-id FARM_ID     The AWS Deadline Cloud Farm ID that the Worker belongs to.
#   --fleet-id FLEET_ID   The AWS Deadline Cloud Fleet ID that the Worker belongs to.
#   --region REGION       The AWS region of the AWS Deadline Cloud farm. If on EC2, this is optional and the region will be automatically detected. Otherwise, this option is required.
#   --user USER           The username of the AWS Deadline Cloud Worker Agent user. Defaults to "deadline-worker-agent".
#   --group GROUP         The group that is shared between the Agent user and the user(s) that jobs run as. Defaults to "deadline-job-users".
#   --start               Starts the service immediately. Defaults to start on system boot. This option is ignored if --no-install-service is used.
#   --allow-shutdown      Controls whether to create/delete a sudoers rule allowing the worker agent OS user to shutdown the system
#   --no-install-service  Skips the worker agent service installation
#   --telemetry-opt-out   Opts out of telemetry data collection
#   --yes, -y             Confirms the installation and skips the interactive confirmation prompt.
#   --vfs-install-path VFS_INSTALL_PATH
#                         Absolute path for the install location of the deadline vfs.
#   --disallow-instance-profile
#                         Disallow running the worker agent with an EC2 instance profile. When this is provided, the worker agent makes requests to the EC2 instance meta-data service (IMDS) to
#                         check for an instance profile. If an instance profile is detected, the worker agent will stop and exit. When this is not provided, the worker agent no longer performs
#                         these checks, allowing it to run with an EC2 instance profile.
#   --session-root-dir SESSION_ROOT_DIR
#                         The root directory under which the worker agent creates session directories


# AWS Deadline Cloud Worker Agent Installer
#
# This script installs the AWS Deadline Cloud Worker Agent.  The installer provides command-line arguments that
# can be used to configure the installation. The installer supports upgrading over top of a prior
# installation, but the installer will not backup or rollback the prior installation.
#
# Minimally, a farm and fleet ID are required options that must be specified as command-line
# arguments. A minimal installation can be run with:
#
#     ./install.sh --farm-id $FARM_ID --fleet-id $FLEET_ID
#
# The installer:
#
#     1.  Creates OS user for the worker agent if required
#     2.  Creates an OS group for all job users if required
#     3.  Provisions directories used by the worker agent at runtime.
#     4.  Creates an agent configuration file if required and installs an example
#         configuration file.
#     5.  Updates the configuration file with arguments passed to the installer
#     6.  Creates, enables, and starts a systemd service unit that runs the worker agent and
#         restarts it upon failure.

delete_user() {
    local username=$1
    
    # Check if user exists
    if dscl . -read /Users/${username} &>/dev/null; then
        echo "Deleting user: ${username}"
        if [ "$VERBOSE_DSCL" = "true" ]; then
            sudo dscl . -delete /Users/${username}
        else
            sudo dscl . -delete /Users/${username} &>/dev/null
        fi
        echo "User ${username} deleted"
    else
        echo "User ${username} does not exist, skipping deletion"
    fi
    
    return 0
}

delete_group() {
    local groupname=$1
    
    # Check if group exists
    if dscl . -read /Groups/${groupname} &>/dev/null; then
        echo "Deleting group: ${groupname}"
        if [ "$VERBOSE_DSCL" = "true" ]; then
            sudo dscl . -delete /Groups/${groupname}
        else
            sudo dscl . -delete /Groups/${groupname} &>/dev/null
        fi
        echo "Group ${groupname} deleted"
    else
        echo "Group ${groupname} does not exist, skipping deletion"
    fi
    
    return 0
}

delete_user_and_group() {
    local username=$1
    local groupname=$2
    
    # Delete the user first
    delete_user "${username}"
    
    # Delete the group
    delete_group "${groupname}"
}

# https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/worker-host.html#create-job-user-and-group

set -euo pipefail

# Set to "true" to show dscl command output, "false" to hide it
VERBOSE_DSCL=${VERBOSE_DSCL:-false}

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

create_group() {
    local groupname=$1

    # Check if group exists
    if dscl . -read /Groups/${groupname} &>/dev/null; then
        # Get the existing group's GID
        if [ "$VERBOSE_DSCL" = "true" ]; then
            local group_gid=$(dscl . -read /Groups/${groupname} PrimaryGroupID | awk '{print $2}')
        else
            local group_gid=$(dscl . -read /Groups/${groupname} PrimaryGroupID 2>/dev/null | awk '{print $2}')
        fi
        echo "Group ${groupname} already exists with GID: ${group_gid}, skipping group creation"
    else
        echo "Creating group: ${groupname}"
        # Get next available GID (501+)
        if [ "$VERBOSE_DSCL" = "true" ]; then
            local group_gid=$(dscl . -list /Groups PrimaryGroupID | awk '{print $2}' | sort -n | tail -1)
        else
            local group_gid=$(dscl . -list /Groups PrimaryGroupID 2>/dev/null | awk '{print $2}' | sort -n | tail -1)
        fi
        group_gid=$((group_gid + 1))
        echo "Using GID: ${group_gid}"

        # Create Group
        if [ "$VERBOSE_DSCL" = "true" ]; then
            sudo dscl . -create /Groups/${groupname}
            sudo dscl . -create /Groups/${groupname} PrimaryGroupID ${group_gid}
        else
            sudo dscl . -create /Groups/${groupname} &>/dev/null
            sudo dscl . -create /Groups/${groupname} PrimaryGroupID ${group_gid} &>/dev/null
        fi
    fi

    return 0
}

create_user() {
    local username=$1
    local groupname=$2  # Primary group
    local realname=$3
    local password=$4   # Optional

    # Get the group's GID
    if [ "$VERBOSE_DSCL" = "true" ]; then
        local group_gid=$(dscl . -read /Groups/${groupname} PrimaryGroupID | awk '{print $2}')
    else
        local group_gid=$(dscl . -read /Groups/${groupname} PrimaryGroupID 2>/dev/null | awk '{print $2}')
    fi
    
    # Check if user exists
    if dscl . -read /Users/${username} &>/dev/null; then
        echo "User ${username} already exists, skipping user creation"
    else
        echo "Creating user: ${username}"
        # Get next available UID (501+)
        if [ "$VERBOSE_DSCL" = "true" ]; then
            local user_uid=$(dscl . -list /Users UniqueID | awk '{print $2}' | sort -n | tail -1)
        else
            local user_uid=$(dscl . -list /Users UniqueID 2>/dev/null | awk '{print $2}' | sort -n | tail -1)
        fi
        user_uid=$((user_uid + 1))
        echo "Using UID: ${user_uid}"

        # Create User
        if [ "$VERBOSE_DSCL" = "true" ]; then
            sudo dscl . -create /Users/${username}
            sudo dscl . -create /Users/${username} UserShell /bin/bash
            sudo dscl . -create /Users/${username} RealName "${realname}"
            sudo dscl . -create /Users/${username} UniqueID ${user_uid}
            sudo dscl . -create /Users/${username} PrimaryGroupID ${group_gid}
            sudo dscl . -create /Users/${username} NFSHomeDirectory /Users/${username}
        else
            sudo dscl . -create /Users/${username} &>/dev/null
            sudo dscl . -create /Users/${username} UserShell /bin/bash &>/dev/null
            sudo dscl . -create /Users/${username} RealName "${realname}" &>/dev/null
            sudo dscl . -create /Users/${username} UniqueID ${user_uid} &>/dev/null
            sudo dscl . -create /Users/${username} PrimaryGroupID ${group_gid} &>/dev/null
            sudo dscl . -create /Users/${username} NFSHomeDirectory /Users/${username} &>/dev/null
        fi

        mkdir /Users/${username}
        chown "${username}:${groupname}" /Users/${username}

        # Set password if provided
        if [ ! -z "$password" ]; then
            echo "Setting password for ${username}"
            if [ "$VERBOSE_DSCL" = "true" ]; then
                sudo dscl . -passwd /Users/${username} ${password}
            else
                sudo dscl . -passwd /Users/${username} ${password} &>/dev/null
            fi
        fi
    fi

    return 0
}

add_user_to_group() {
    local username=$1
    local groupname=$2

    # Check if user is already in group
    if [ "$VERBOSE_DSCL" = "true" ]; then
        local check_result=$(dscl . -read /Groups/${groupname} GroupMembership 2>/dev/null || echo "")
    else
        local check_result=$(dscl . -read /Groups/${groupname} GroupMembership 2>/dev/null || echo "")
    fi
    if echo "$check_result" | grep -q "${username}"; then
        echo "User ${username} is already a member of group ${groupname}"
    else
        echo "Adding user ${username} to group ${groupname}"
        # Add user to group
        if [ "$VERBOSE_DSCL" = "true" ]; then
            sudo dscl . -append /Groups/${groupname} GroupMembership ${username}
        else
            sudo dscl . -append /Groups/${groupname} GroupMembership ${username} &>/dev/null
        fi
    fi
    
    return 0
}

# Function to create a user and its group
create_user_and_group() {
    local username=$1
    local groupname=$2
    local realname=$3
    local password=$4  # Optional

    # Create the group first
    create_group "${groupname}"
    
    # Create the user with the group as primary group
    create_user "${username}" "${groupname}" "${realname}" "${password}"
    
    # Add the user to the group (redundant for primary group, but ensures membership)
    add_user_to_group "${username}" "${groupname}"
}

export JOB_USERS_GROUP=deadline-job-users

export WORKER_AGENT_USER=deadline-worker-agent
export WORKER_AGENT_GROUP=deadline-worker-agent

export QUEUE_USER=deadline-qa-user
export QUEUE_GROUP=deadline-qa-user

# Create the worker agent user and group
create_user_and_group "${WORKER_AGENT_USER}" "${WORKER_AGENT_GROUP}" "Deadline Cloud Worker Agent" ""

# Create the queue's job user and group
create_user_and_group "${QUEUE_USER}" "${QUEUE_GROUP}" "Deadline Cloud Queue User" "test-user-password"

# Create the shared job users group and add queue user/worker agent user to it
create_group "${JOB_USERS_GROUP}"
add_user_to_group "${QUEUE_USER}" "${JOB_USERS_GROUP}"
add_user_to_group "${WORKER_AGENT_USER}" "${JOB_USERS_GROUP}"

echo "Provisioning log directory (/var/log/amazon/deadline)"
mkdir -p /var/log/amazon/deadline
chmod 755 /var/log/amazon
chown -R "${WORKER_AGENT_USER}:${WORKER_AGENT_GROUP}" /var/log/amazon/deadline
chmod -R 750 /var/log/amazon/deadline
echo "Done provisioning log directory (/var/log/amazon/deadline)"

# Provision ownership/persistence on persistence directory
echo "Provisioning persistence directory (/var/lib/deadline)"
mkdir -p /var/lib/deadline/queues
mkdir -p /var/lib/deadline/credentials
chown "${WORKER_AGENT_USER}:${JOB_USERS_GROUP}" \
    /var/lib/deadline \
    /var/lib/deadline/queues
chown "${WORKER_AGENT_USER}" /var/lib/deadline/credentials
chmod 750 \
    /var/lib/deadline \
    /var/lib/deadline/queues
chmod 700 \
    /var/lib/deadline/credentials
if [ -f /var/lib/deadline/worker.json ]; then
    chown "${WORKER_AGENT_USER}:${WORKER_AGENT_GROUP}" /var/lib/deadline/worker.json
    chmod 600 /var/lib/deadline/worker.json
fi
echo "Done provisioning persistence directory (/var/lib/deadline)"

# Provision session directory
export SESSION_ROOT_DIR="/Library/Application Support/Deadline Cloud Worker"
echo "Provisioning root directory for OpenJD Sessions (${SESSION_ROOT_DIR})"
mkdir -p "${SESSION_ROOT_DIR}"
chown "${WORKER_AGENT_USER}:${JOB_USERS_GROUP}" "${SESSION_ROOT_DIR}"
chmod 755 "${SESSION_ROOT_DIR}"
echo "Done provisioning root directory for OpenJD Sessions (${SESSION_ROOT_DIR})"

echo "Provisioning configuration directory (/etc/amazon/deadline)"
mkdir -p /etc/amazon/deadline
chmod 750 /etc/amazon/deadline
# Copy the example configuration file
cp "${SCRIPT_DIR}/worker.toml.example" /etc/amazon/deadline/
if [ ! -f /etc/amazon/deadline/worker.toml ]; then
    cp "${SCRIPT_DIR}/worker.toml.example" /etc/amazon/deadline/worker.toml
fi
# Ensure the config file has secure permissions
chown -R "root:${WORKER_AGENT_GROUP}" /etc/amazon/deadline
chmod 640 /etc/amazon/deadline/worker.toml
echo "Done provisioning configuration directory"

echo "Done installing worker agent"

