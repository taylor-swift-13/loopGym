int unknown();
void foo272() {

    int i;
    int j;
    int k;

    i = 0;
    j = 0;


        k = unknown();

    while (i <= k) {
       i++;
       j = j + 1;
      }

    /*@ assert i == j; */

  }