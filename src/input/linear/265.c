int unknown();
/*@ requires l > 0; */
void foo265(int l) {

    int n;
    int i;

    i = l;


        n = unknown();

    while (i < n) {
       i = i + 1;
      }

    /*@ assert l >= 1; */

  }