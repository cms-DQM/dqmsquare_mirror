# Tests to check DB and data filling and fetching
import os
import sys
from sqlalchemy.engine.row import RowMapping

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from decorators import PAGINATION_DEFAULT_ITEMS_PER_PAGE
from db import DQM2MirrorDB

# Needed to be passed as a fixture
from fixtures import testing_database, get_valid_metadata


class TestPagination:
    def test_fill_and_get(self, testing_database: DQM2MirrorDB):
        MULTIPLE_OF_ITEMS_PER_PAGE = 2
        MAX_ELEMENTS = PAGINATION_DEFAULT_ITEMS_PER_PAGE * MULTIPLE_OF_ITEMS_PER_PAGE
        for i in range(0, MAX_ELEMENTS):
            testing_database.fill_cmssw_comparison_report(
                **get_valid_metadata(i),
            )
        r = testing_database.get_cmssw_comparison_reports(paginate=True)
        assert all([key in r for key in ["page", "total_pages"]])
        assert (
            r["page"] == 1
            and r["total_pages"] == MULTIPLE_OF_ITEMS_PER_PAGE
            and isinstance(r["data"], list)
            and isinstance(r["data"][0], RowMapping)
        )
        r2 = testing_database.get_cmssw_comparison_reports(paginate=True, page=1)
        assert r == r2
        r3 = testing_database.get_cmssw_comparison_reports(paginate=True, page=2)
        assert r3["page"] == 2 and r3["total_pages"] == MULTIPLE_OF_ITEMS_PER_PAGE
