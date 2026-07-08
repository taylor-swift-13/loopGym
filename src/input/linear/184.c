int unknown();
/*@ requires n == 1 || n == 2; */
void foo184(int n) {

    int i;
    int j;
    int k;

    i = 0;
    j = 0;


        k = unknown();

    while(i <= k){
       i = i + 1;
       j = j + n;
      }

    /*@ assert (i > k && n == 1) ==> (i == j); */

  }