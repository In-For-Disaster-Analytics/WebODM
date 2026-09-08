import ProjectListItem from '../ProjectListItem';

function makeFile(name, type, relPath){
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, 'webkitRelativePath', { value: relPath });
  return f;
}

// Instantiate the component class directly (no DOM mount, no
// componentDidMount) so the class-field arrow-function methods exist as
// real bound instance methods, without pulling in Dropzone/NewTaskPanel/
// EditTaskForm and their AJAX calls, which are unrelated to this logic.
function makeInstance(){
  const fakeHistory = { location: { pathname: "/", search: "", hash: "" } };
  const projectMock = {
    id: 1, name: "Test", description: "", owned: true,
    permissions: ["add"], tasks: [], tags: []
  };
  const instance = new ProjectListItem({ history: fakeHistory, data: projectMock });
  instance.dz = {
    options: { acceptedFiles: "image/*,text/plain,.las,.laz,video/*,.srt,.dng,.nef" },
    addFile: jest.fn(),
    emit: jest.fn()
  };
  return instance;
}

describe('ProjectListItem directory-select chaining logic', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('adds only accepted files and keeps reopening the picker until the user cancels', () => {
    const instance = makeInstance();

    // First folder: 2 images + 1 junk file Dropzone should never see
    const folderA = { click: jest.fn(), value: "x" };
    folderA.files = [
      makeFile("DJI_0001.jpg", "image/jpeg", "FolderA/DJI_0001.jpg"),
      makeFile("DJI_0002.jpg", "image/jpeg", "FolderA/DJI_0002.jpg"),
      makeFile(".DS_Store", "", "FolderA/.DS_Store"),
    ];
    instance.handleDirectorySelect({ target: folderA });

    expect(instance.dz.addFile).toHaveBeenCalledTimes(2);
    expect(instance.dz.emit).toHaveBeenCalledWith("addedfiles", expect.arrayContaining([folderA.files[0], folderA.files[1]]));
    expect(instance.dz.emit.mock.calls[0][1].length).toBe(2); // junk file silently dropped
    expect(folderA.value).toBe(""); // input reset so the same folder can be picked again

    jest.runAllTimers();
    expect(folderA.click).toHaveBeenCalledTimes(1); // dialog chained to pick another folder

    // Second folder: 1 more image
    const folderB = { click: jest.fn(), value: "x" };
    folderB.files = [makeFile("DJI_0001.jpg", "image/jpeg", "FolderB/DJI_0001.jpg")];
    instance.handleDirectorySelect({ target: folderB });
    expect(instance.dz.addFile).toHaveBeenCalledTimes(3);

    jest.runAllTimers();
    expect(folderB.click).toHaveBeenCalledTimes(1);

    // User cancels: browsers don't fire "change" with an empty FileList on
    // cancel, but even if something did, the chain must not reopen.
    const folderC = { click: jest.fn(), value: "x", files: [] };
    instance.handleDirectorySelect({ target: folderC });

    jest.runAllTimers();
    expect(folderC.click).not.toHaveBeenCalled();

    expect(instance.dz.emit).toHaveBeenCalledTimes(2); // only the two non-empty batches emitted "addedfiles"
  });

  it('does not reopen the picker when a folder has nothing acceptable in it', () => {
    const instance = makeInstance();
    const folder = { click: jest.fn(), value: "x" };
    // Non-empty FileList, but nothing matches acceptedFiles.
    folder.files = [makeFile("readme.md", "text/markdown", "Folder/readme.md")];

    instance.handleDirectorySelect({ target: folder });
    expect(instance.dz.addFile).not.toHaveBeenCalled();
    expect(instance.dz.emit).not.toHaveBeenCalled();

    jest.runAllTimers();
    // allFiles.length > 0 (the folder wasn't empty/canceled), so the
    // chain still reopens even though every file was filtered out --
    // otherwise picking an all-junk folder would silently kill the loop.
    expect(folder.click).toHaveBeenCalledTimes(1);
  });
});
