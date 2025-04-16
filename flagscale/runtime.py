import os
import sys
import shutil
import tempfile
from git.repo import Repo
import argparse


DELETED_FILE_NAME = "deleted_files.txt"
def unpatch(src, dst, submodule_name):
    init_submodule(dst, submodule_name)
    create_symlinks(src, dst)
    deleted_files_path = os.path.join(src, DELETED_FILE_NAME)
    if os.path.lexists(deleted_files_path):
        delete_file(deleted_files_path, dst)


def delete_file(file_path, dst):
    with open(file_path, "r", encoding="utf-8") as f:
        deleted_files = f.readlines()
        for deleted_file in deleted_files:
            deleted_file = deleted_file.strip()
            deleted_file_path = os.path.join(dst, deleted_file)
            if os.path.lexists(deleted_file_path):
                os.remove(deleted_file_path)
                print(f"Deleted file: {deleted_file_path}")
            else:
                print(f"File not found for deletion: {deleted_file_path}")


def create_symlinks(src, dst):
    for root, dirs, files in os.walk(src):
        for filename in files:
            src_file = os.path.join(root, filename)
            if src_file == os.path.join(src, DELETED_FILE_NAME):
                continue
            
            rel_path = os.path.relpath(src_file, src)
            dst_file = os.path.join(dst, rel_path)

            dst_file_dir = os.path.dirname(dst_file)
            if not os.path.lexists(dst_file_dir):
                os.makedirs(dst_file_dir)

            if os.path.lexists(dst_file):
                os.remove(dst_file)
            assert not os.path.lexists(dst_file)
            os.symlink(src_file, dst_file)

            print(f"Created symbolic link: {dst_file} -> {src_file}")


def init_submodule(dst, submodule_name):
    if os.path.lexists(dst) and len(os.listdir(dst)) > 0:
        print(f"Skipping {submodule_name} initialization, as it already lexists.")
        return
    print(f"Initializing submodule {submodule_name}...")
    repo = Repo(os.path.dirname(os.path.dirname(__file__)))
    repo.submodule_update(init=True, recursive=True)
    print(f"Initialized {submodule_name} submodule.")


def patch(main_path, submodule_name, src, dst):
    main_repo = Repo(main_path)
    # raise ValueError(help(main_repo.submodule))
    submodule = main_repo.submodule(submodule_name)
    sub_repo = submodule.module()
    base_commit_hash = submodule.hexsha
    print(f"Base commit hash of submodule {submodule_name} is {base_commit_hash}.")

    # Get submodule commit tree
    base_commit = sub_repo.commit(base_commit_hash)
    base_tree = base_commit.tree

    index = sub_repo.index
    index_tree_hash = index.write_tree()

    status_mapping = {
        'A': 'new',
        'D': 'deleted',
        'M': 'modified',
        'R': 'renamed',
        'T': 'typechange',
        'U': 'unmerged',
        'UT': 'untracked'
    }
    file_statuses = {}

    # Get diff with base commit
    diff_index = base_tree.diff(index_tree_hash)
    # Process the diff between the staged and the base commit
    for diff in diff_index:
        if diff.new_file:
            status = 'A'
            file_path = diff.b_path
            file_statuses[file_path] = [status]
        elif diff.deleted_file:
            status = 'D'
            file_path = diff.a_path
            file_statuses[file_path] = [status]
        elif diff.renamed_file:
            status = 'R'
            file_path = diff.b_path
            file_statuses[diff.a_path] = [status, file_path]
        elif diff.change_type == 'M':
            status = 'M'
            assert diff.a_path == diff.b_path
            file_path = diff.b_path
            file_statuses[file_path] = [status]
        elif diff.change_type == 'T':
            status = 'T'
            assert diff.a_path == diff.b_path
            file_path = diff.b_path
            file_statuses[file_path] = [status]
        elif diff.change_type == 'U':
            raise ValueError(f"Unmerged status is not supported.")
        else:
            raise ValueError(f"Unsupported  status: {diff.change_type}.")

    # Get diff with working directory
    diff_workdir = index.diff(None)
    # Process the diff between the working directory and the staged
    for diff in diff_workdir:
        if diff.new_file:
            status = 'A'
            file_path = diff.b_path
            file_statuses[file_path] = [status]
        elif diff.deleted_file:
            status = 'D'
            file_path = diff.a_path
            file_statuses[file_path] = [status]
        elif diff.renamed_file:
            status = 'R'
            file_path = diff.b_path
            file_statuses[diff.a_path] = [status, file_path]
        elif diff.change_type == 'M':
            status = 'M'
            assert diff.a_path == diff.b_path
            file_path = diff.b_path
            file_statuses[file_path] = [status]
        elif diff.change_type == 'T':
            status = 'T'
            assert diff.a_path == diff.b_path
            file_path = diff.b_path
            file_statuses[file_path] = [status]
        elif diff.change_type == 'U':
            raise ValueError(f"Unmerged status is not supported.")
        else:
            raise ValueError(f"Unsupported  status: {diff.change_type}.")
        file_statuses[file_path] = status

    # Get untracked files
    untracked_files = sub_repo.untracked_files
    for file in untracked_files:
        file_statuses[file] = ['UT']
    
    # The file status may be overwritten, so we follow the sequence of staged, working dir, untracked.
    print(file_statuses)

    file_status_deleted = {}
    tmp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False)
    for file_path in file_statuses:
        if file_statuses[file_path][0] == 'D':
            file_status_deleted[file_path] = file_statuses[file_path]

    for file_path in file_statuses:
        if file_statuses[file_path][0] == 'D':
            continue
        sync(file_path, file_statuses[file_path], src, dst, tmp_file)

    # Process the deleted files
    if file_status_deleted:
        try:
            for file_path in file_status_deleted:
                assert file_statuses[file_path][0] == 'D'
                sync(file_path, file_status_deleted[file_path], src, dst, tmp_file)
            deleted_log = os.path.join(src, "deleted_files.log")
            tmp_file.close()

            shutil.move(tmp_file.name, deleted_log)
            if os.path.lexists(tmp_file.name):
                os.remove(tmp_file.name)

        except Exception as e:
            print(f"Error occurred while processing deleted files: {e}")
            tmp_file.close()
            if os.path.lexists(tmp_file.name):
                os.remove(tmp_file.name)
            raise
        

    return file_statuses


def sync(file_path, status, src, dst, f=None):
    src_file_path = os.path.join(src, file_path)
    dst_file_path = os.path.join(dst, file_path)
    change_type = status[0]

    symbolic_error = "Defining symbolic links in the submodule is not supported except for those defined in FlagScale"
    typechange_error = "File type changes are not supported in the submodule"
    if change_type == 'T':
        is_symlink = os.path.islink(dst_file_path)
        if is_symlink:
            if not os.path.lexists(src_file_path):
                raise ValueError(f"{symbolic_error}: {dst_file_path}")
        else:
            raise ValueError(f"{typechange_error}: {dst_file_path}")

    elif change_type in ['A', 'UT']:
        is_symlink = os.path.islink(dst_file_path)
        if is_symlink:
            if not os.path.lexists(src_file_path):
                real_path = os.readlink(dst_file_path)
                if os.path.lexists(real_path):
                    os.makedirs(os.path.dirname(src_file_path), exist_ok=True)
                    shutil.move(real_path, src_file_path)
                    print(f"Move {real_path} to {src_file_path} and create symbolic link {dst_file_path} -> {src_file_path}")
                    if os.path.lexists(dst_file_path):
                        os.remove(dst_file_path)
                    os.symlink(src_file_path, dst_file_path)
                else:
                    raise ValueError(f"{symbolic_error}: {dst_file_path}")
        else:
            create_file_and_symlink(src_file_path, dst_file_path)

    elif change_type == 'D':
        if os.path.lexists(src_file_path):
            os.remove(src_file_path)
            print(f"The file {src_file_path} has been deleted.")
        else:
            assert f
            f.write(f"{file_path}\n")
            f.flush()

    elif change_type == 'M':
        is_symlink = os.path.islink(dst_file_path)
        if is_symlink:
            raise ValueError("Modified symbolic links in the submodule is not supported except for those defined in FlagScale")
        if not os.path.lexists(src_file_path):
            create_file_and_symlink(src_file_path, dst_file_path)

    elif change_type == 'R':
        assert len(status) == 2
        rel_dst_path = status[1]
        renamed_dst_file_path = os.path.join(dst, rel_dst_path)
        is_symlink = os.path.islink(renamed_dst_file_path)
        renamed_src_file_path = os.path.join(src, rel_dst_path)
        if is_symlink:
            real_path = os.readlink(renamed_dst_file_path)
            os.makedirs(os.path.dirname(renamed_src_file_path), exist_ok=True)
            if real_path != renamed_src_file_path:
                shutil.move(real_path, renamed_src_file_path)
                print(f"Move {real_path} to {renamed_src_file_path} and create symbolic link {renamed_dst_file_path} -> {renamed_src_file_path}")
            if os.path.lexists(renamed_dst_file_path):
                os.remove(renamed_dst_file_path)
            os.symlink(renamed_src_file_path, renamed_dst_file_path)
        else:
            assert not os.path.lexists(renamed_src_file_path)
            create_file_and_symlink(renamed_src_file_path, renamed_dst_file_path)
            assert f
            f.write(f"{file_path}\n")
            f.flush()


def create_file_and_symlink(source_file, target_file):
    assert not os.path.lexists(source_file)
    assert os.path.lexists(target_file)

    source_dir = os.path.dirname(source_file)
    if not os.path.lexists(source_dir):
        os.makedirs(source_dir, exist_ok=True)

    shutil.copyfile(target_file, source_file)
    if os.path.lexists(target_file):
        os.remove(target_file)
    os.symlink(source_file, target_file)
    print(f"The file {target_file} has been copied to {source_file} and Create symbolic link {target_file} -> {source_file}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch or unpatch backend with symlinks.")
    parser.add_argument('--action', choices=["patch", "unpatch"], default="unpatch",
                        help="Action to perform: patch or unpatch (default: unpatch)")
    parser.add_argument('--backend', choices=["Megatron-LM", "vllm"], default="Megatron-LM",
                        help="Backend to process (default: Megatron-LM)")

    args = parser.parse_args()
    action = args.action
    backend = args.backend

    script_dir = os.path.dirname(os.path.realpath(__file__))
    main_path = os.path.dirname(script_dir)

    submodule_name = f"third_party/{backend}"
    # Megatron-LM
    if backend == "Megatron-LM":
        src = os.path.join(script_dir, "train", backend)
        dst = os.path.join(script_dir, "..", "third_party", backend)
        if action == "unpatch":
            unpatch(src, dst, submodule_name)
        elif action == "patch":
            patch(main_path, submodule_name, src, dst)

    # # vllm will be supported in the future
    # elif backend == "vllm":
    # src = os.path.join(script_dir, "train", "vllm")
    # dst = os.path.join(script_dir, "..", "third_party", "vllm")
    # create_symlinks(src, dst)

    # Other backends will be supported in the future.
