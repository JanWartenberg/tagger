from tagger_app.photo_workspace import PhotoWorkspace


def test_refresh_preserves_filters_selection_and_iptc_membership():
    workspace = PhotoWorkspace()
    workspace.reload_paths(["/birds/old.jpg", "/birds/keep.jpg", "/other/keep.jpg"])
    workspace.select_paths(["/birds/keep.jpg"])
    workspace.set_filename_filter("keep")
    workspace.start_indexed_iptc_empty_filter()
    operation = workspace.snapshot().filter_operation_id
    workspace.accept_indexed_iptc_empty_filter(operation, ["/birds/keep.jpg"])

    snapshot = workspace.refresh_paths(["/birds/new.jpg"], ["/birds/old.jpg"])

    assert snapshot.paths == ("/birds/keep.jpg", "/other/keep.jpg", "/birds/new.jpg")
    assert snapshot.visible_paths == ("/birds/keep.jpg",)
    assert snapshot.selected_paths == ("/birds/keep.jpg",)
    assert snapshot.filename_filter_query == "keep"
    assert workspace.clear_iptc_empty_filter().visible_paths == (
        "/birds/keep.jpg",
        "/other/keep.jpg",
    )


def test_refresh_updates_folder_restore_state_without_polluting_search():
    workspace = PhotoWorkspace()
    workspace.reload_paths(["/birds/old.jpg", "/other/keep.jpg"])
    workspace.apply_database_search_matches(["/birds/old.jpg"])

    snapshot = workspace.refresh_paths(["/birds/new.jpg"], ["/birds/old.jpg"])

    assert snapshot.visible_paths == ()
    restored = workspace.clear_database_search()
    assert restored.paths == ("/other/keep.jpg", "/birds/new.jpg")


def test_refresh_keeps_directory_exclusions_and_unrelated_workspace_members():
    workspace = PhotoWorkspace()
    workspace.reload_paths(["/other/keep.jpg", "/birds/gone.jpg"])
    workspace.add_directory_exclusion("hidden")
    snapshot = workspace.refresh_paths(
        ["/birds/hidden/new.jpg", "/birds/shown.jpg"], ["/birds/gone.jpg"]
    )
    assert snapshot.visible_paths == ("/other/keep.jpg", "/birds/shown.jpg")
    assert snapshot.excluded_directory_names == ("hidden",)
